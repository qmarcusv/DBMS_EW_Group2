/* Phase 3 UC1. Run after uc1_setup.js from DBMS_Group2 workspace root.
   Writes ONLY uc1_* copies. Emits one EJSON object per line; capture stdout.
   A/B/C read copy is reset by changing only its experiment index.
   Three independent write copies begin from the same 100K source image. */
load("mongo/benchmark/benchmark_core.js");
(() => {
  const auditDb = db.getSiblingDB("dbms_ew_group02");
  const source = auditDb.getCollection("big_table_100k");
  const readCopy = auditDb.getCollection("uc1_bench_100K");
  const writeNames = { A: "uc1_write_A_100K", B: "uc1_write_B_100K", C: "uc1_write_C_100K" };
  const runId = "UC1-" + new Date().toISOString() + "-" + Math.floor(Math.random() * 1000000);
  const projection = { _id: 0, ID: 1, OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1 };
  const queries = [
    { id: "U1a", filter: { OWNER: "SYS", OBJECT_TYPE: "TABLE", OBJECT_ID: 16 }, count: 2 },
    { id: "U1b", filter: { OWNER: "SYS", OBJECT_TYPE: "TABLE" }, count: 3405 },
    { id: "U1c", filter: { OBJECT_TYPE: "TABLE", OBJECT_ID: 16 }, count: 2 },
    { id: "U1d", filter: { OWNER: "CTXSYS" }, sort: { OBJECT_TYPE: 1, OBJECT_ID: 1 }, count: 398 },
  ];
  const warmups = 2,
    repetitions = 25,
    writeBatches = 20,
    batchSize = 1000;
  const expected = new Map();
  function emit(section, fields) {
    print(EJSON.stringify({ section, run_id: runId, ...fields }));
  }
  function assertOnlyIndexes(collection, expectedNames) {
    const names = collection
      .getIndexes()
      .map((i) => i.name)
      .sort();
    if (JSON.stringify(names) !== JSON.stringify([...expectedNames].sort())) throw new Error("Unexpected index inventory on " + collection.getName() + ": " + names);
  }
  function inspectSource() {
    if (!auditDb.getCollectionNames().includes("big_table_100k") || source.countDocuments({}) !== 100000 || readCopy.countDocuments({}) !== 100000) throw new Error("Source/read copy missing or row count changed");
    for (const name of Object.values(writeNames)) {
      if (!auditDb.getCollectionNames().includes(name) || auditDb.getCollection(name).countDocuments({}) !== 100000) throw new Error("Write copy missing or already mutated: " + name);
    }
    assertOnlyIndexes(readCopy, ["_id_"]);
    for (const name of Object.values(writeNames)) assertOnlyIndexes(auditDb.getCollection(name), ["_id_"]);
    for (const q of queries) {
      const actual = source.countDocuments(q.filter);
      if (actual !== q.count) throw new Error(q.id + " source count changed: " + actual);
      const sourceSum = source.aggregate([{ $match: q.filter }, { $group: { _id: null, id_sum: { $sum: "$ID" }, object_id_sum: { $sum: "$OBJECT_ID" } } }]).toArray()[0];
      expected.set(q.id, { count: actual, id_sum: Number(sourceSum.id_sum), object_id_sum: Number(sourceSum.object_id_sum) });
      emit("QUERY_SELECTIVITY", { query_id: q.id, predicate: q.filter, sort: q.sort || null, matching_rows: actual, selectivity: actual / 100000, expected: expected.get(q.id) });
    }
    emit("ENVIRONMENT", { database: auditDb.getName(), version: auditDb.version(), source: source.getName(), source_indexes: source.getIndexes(), read_copy_indexes: readCopy.getIndexes(), warmups, repetitions, timing_method: "mongosh performance.now; full cursor consumption" });
  }

  function measureQuery(configuration, q) {
    const raw = [];
    const target = expected.get(q.id);
    for (let iteration = -warmups; iteration < repetitions; iteration++) {
      let count = 0,
        idSum = 0,
        objectIdSum = 0;
      const started = performance.now();
      let cursor = readCopy.find(q.filter, projection);
      if (q.sort) cursor = cursor.sort(q.sort);
      cursor.forEach((doc) => {
        count++;
        idSum += doc.ID;
        objectIdSum += doc.OBJECT_ID;
      });
      const elapsed = performance.now() - started;
      const correct = count === target.count && idSum === target.id_sum && objectIdSum === target.object_id_sum;
      if (!correct) throw new Error(q.id + " result changed in " + configuration);
      if (iteration >= 0) raw.push({ iteration: iteration + 1, elapsed_ms: elapsed, returned_rows: count, id_sum: idSum, object_id_sum: objectIdSum, correctness_status: "PASS" });
    }
    const summary = BenchmarkCore.summarize(raw);
    emit("READ_RAW", { configuration, query_id: q.id, samples: raw });
    emit("READ_SUMMARY", { configuration, query_id: q.id, matched_rows: target.count, selectivity: target.count / 100000, warmup_count: warmups, ...summary, correctness_status: "PASS", timing_method: "performance.now; full cursor" });
    const diagnostic = BenchmarkCore.explainFind(readCopy, q.filter, projection, q.sort);
    if (diagnostic.returned_rows !== target.count) throw new Error(q.id + " explain result count changed");
    emit("READ_PLAN", { configuration, query_id: q.id, ...diagnostic });
  }

  function readConfigurations() {
    for (const configuration of ["A", "B", "C"]) {
      if (configuration === "B") {
        const build = BenchmarkCore.timeIndexBuild(readCopy, { OWNER: 1 }, { name: "ix_uc1_owner" });
        emit("INDEX_BUILD", { configuration, ...build });
      } else if (configuration === "C") {
        readCopy.dropIndex("ix_uc1_owner");
        const build = BenchmarkCore.timeIndexBuild(readCopy, { OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1 }, { name: "ix_uc1_owner_type_object_id" });
        emit("INDEX_BUILD", { configuration, ...build });
      }
      const expectedNames = configuration === "A" ? ["_id_"] : configuration === "B" ? ["_id_", "ix_uc1_owner"] : ["_id_", "ix_uc1_owner_type_object_id"];
      assertOnlyIndexes(readCopy, expectedNames);
      emit("INDEX_INVENTORY", { configuration, ...BenchmarkCore.indexInventory(readCopy) });
      for (const q of queries) measureQuery(configuration, q);
      if (readCopy.countDocuments({}) !== 100000) throw new Error("Read copy was modified");
    }
  }

  function writeProbes() {
    const seed = source.find({ ID: { $gte: 1, $lte: batchSize } }).toArray();
    if (seed.length !== batchSize) throw new Error("Write seed batch incomplete");
    for (const configuration of ["A", "B", "C"]) {
      const copy = auditDb.getCollection(writeNames[configuration]);
      if (configuration === "B") copy.createIndex({ OWNER: 1 }, { name: "ix_uc1_owner" });
      if (configuration === "C") copy.createIndex({ OWNER: 1, OBJECT_TYPE: 1, OBJECT_ID: 1 }, { name: "ix_uc1_owner_type_object_id" });
      const expectedNames = configuration === "A" ? ["_id_"] : configuration === "B" ? ["_id_", "ix_uc1_owner"] : ["_id_", "ix_uc1_owner_type_object_id"];
      assertOnlyIndexes(copy, expectedNames);
      emit("WRITE_COPY_INDEXES", { configuration, indexes: copy.getIndexes(), note: "Write-copy index preparation excluded from measured index build time." });

      const inserts = [],
        updates = [];
      for (let batch = 0; batch < writeBatches; batch++) {
        const docs = seed.map((original) => {
          const doc = { ...original, ID: original.ID + 1000000 + batch * batchSize };
          delete doc._id;
          return doc;
        });
        const started = performance.now();
        const result = copy.insertMany(docs);
        const elapsed = performance.now() - started;
        const inserted = Object.keys(result.insertedIds).length;
        if (inserted !== batchSize) throw new Error("INSERT batch incomplete");
        inserts.push({ batch: batch + 1, rows: inserted, elapsed_ms: elapsed });
      }
      if (copy.countDocuments({}) !== 100000 + writeBatches * batchSize) throw new Error("INSERT total incorrect");
      for (let batch = 0; batch < writeBatches; batch++) {
        const low = batch * batchSize + 1,
          high = (batch + 1) * batchSize;
        const started = performance.now();
        const result = copy.updateMany({ ID: { $gte: low, $lte: high } }, { $set: { OWNER: "UC1_UPDATED" } });
        const elapsed = performance.now() - started;
        if (result.matchedCount !== batchSize || result.modifiedCount !== batchSize) throw new Error("UPDATE batch incomplete");
        updates.push({ batch: batch + 1, matched: result.matchedCount, modified: result.modifiedCount, elapsed_ms: elapsed });
      }
      emit("WRITE_RAW", { configuration, inserts, updates });
      const insertMs = inserts.reduce((sum, item) => sum + item.elapsed_ms, 0);
      const updateSummary = BenchmarkCore.summarize(updates);
      emit("WRITE_SUMMARY", {
        configuration,
        insert_rows: writeBatches * batchSize,
        insert_elapsed_ms: insertMs,
        insert_rows_per_second: (writeBatches * batchSize * 1000) / insertMs,
        update_batches: writeBatches,
        update_rows_per_batch: batchSize,
        update_median_ms: updateSummary.query_median_ms,
        update_p95_ms: updateSummary.query_p95_ms,
        final_rows: copy.countDocuments({}),
        updated_rows: copy.countDocuments({ OWNER: "UC1_UPDATED" }),
      });
    }
  }

  inspectSource();
  readConfigurations();
  writeProbes();
  emit("RUN_COMPLETE", { status: "PASS", read_copy: readCopy.getName(), write_copies: Object.values(writeNames), source_unchanged_rows: source.countDocuments({}) });
})();
