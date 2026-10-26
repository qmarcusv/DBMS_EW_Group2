/* Phase 5 UC3. Run from DBMS_Group2 root with mongosh --quiet --file.
   Creates only uc3_* disposable copies. Save JSONL before cleanup. */
load("mongo/benchmark/benchmark_core.js");
(() => {
  const d = db.getSiblingDB("dbms_ew_group02");
  const run = "UC3-" + new Date().toISOString();
  const emit = (section, data) => print(EJSON.stringify({ section, run_id: run, ...data }));
  const scales = [
    { label: "100K", source: "big_table_100k", rows: 100000, small: 50, medium: 1000 },
    { label: "1000K", source: "big_table_1000K", rows: 1000000, small: 5, medium: 200 },
  ];
  const keysB = { OBJECT_ID: 1 };
  const keysC = { OBJECT_ID: 1, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1 };
  const projection = { _id: 0, ID: 1, OWNER: 1, OBJECT_NAME: 1, OBJECT_TYPE: 1 };
  const names = scales.flatMap((s) => ["uc3_bench_" + s.label, ...["A", "B", "C"].map((c) => "uc3_write_" + c + "_" + s.label)]);
  const existing = d.getCollectionNames();
  if (d.version().split(".")[0] !== "7") throw new Error("MongoDB 7.x required");
  for (const name of names) if (existing.includes(name)) throw new Error("Copy already exists: " + name);
  for (const s of scales) {
    if (!existing.includes(s.source) || d.getCollection(s.source).countDocuments({}) !== s.rows) throw new Error("Source missing or count changed: " + s.source);
  }
  emit("ENVIRONMENT", { database: d.getName(), version: d.version(), scales });
  const signature = (x) => JSON.stringify([x.ID, x.OWNER, x.OBJECT_NAME, x.OBJECT_TYPE]);
  for (const s of scales) {
    const source = d.getCollection(s.source);
    const read = d.getCollection("uc3_bench_" + s.label);
    const writeNames = Object.fromEntries(["A", "B", "C"].map((c) => [c, "uc3_write_" + c + "_" + s.label]));
    for (const name of [read.getName(), ...Object.values(writeNames)]) {
      source.aggregate([{ $out: name }]).toArray();
      const copy = d.getCollection(name);
      if (copy.countDocuments({}) !== s.rows || JSON.stringify(copy.getIndexes().map((i) => i.name)) !== '["_id_"]') throw new Error("Copy count/index mismatch: " + name);
      emit("COPY_READY", { scale: s.label, name, rows: s.rows, indexes: copy.getIndexes() });
    }
    const workload = [
      { id: "POINT", filter: { OBJECT_ID: 16, ID: 1 } },
      { id: "SMALL", filter: { OBJECT_ID: { $gte: 1, $lte: s.small } } },
      { id: "MEDIUM", filter: { OBJECT_ID: { $gte: 1, $lte: s.medium } } },
    ];
    const expected = Object.fromEntries(
      workload.map((q) => {
        const docs = source.find(q.filter, projection).toArray().map(signature).sort();
        if (!docs.length) throw new Error("Empty workload: " + s.label + q.id);
        emit("QUERY_SELECTIVITY", { scale: s.label, query_id: q.id, filter: q.filter, matched_rows: docs.length, selectivity: docs.length / s.rows });
        return [q.id, docs];
      }),
    );
    for (const config of ["A", "B", "C"]) {
      if (config === "B") emit("INDEX_BUILD", { scale: s.label, config, ...BenchmarkCore.timeIndexBuild(read, keysB, { name: "ix_uc3_key" }) });
      if (config === "C") {
        read.dropIndex("ix_uc3_key");
        emit("INDEX_BUILD", { scale: s.label, config, ...BenchmarkCore.timeIndexBuild(read, keysC, { name: "ix_uc3_cover" }) });
      }
      emit("INDEX_INVENTORY", { scale: s.label, config, ...BenchmarkCore.indexInventory(read) });
      for (const q of workload) {
        const samples = [];
        for (let i = -2; i < 25; i++) {
          const start = performance.now();
          const docs = read.find(q.filter, projection).toArray();
          const elapsed_ms = performance.now() - start;
          if (JSON.stringify(docs.map(signature).sort()) !== JSON.stringify(expected[q.id])) throw new Error("Result mismatch: " + s.label + config + q.id);
          if (i >= 0) samples.push({ iteration: i + 1, elapsed_ms, matched_rows: docs.length });
        }
        emit("READ_RAW", { scale: s.label, config, query_id: q.id, samples });
        emit("READ_SUMMARY", { scale: s.label, config, query_id: q.id, matched_rows: expected[q.id].length, warmups: 2, ...BenchmarkCore.summarize(samples) });
        const diag = BenchmarkCore.explainFind(read, q.filter, projection);
        if (diag.returned_rows !== expected[q.id].length) throw new Error("Plan result mismatch");
        emit("READ_PLAN", { scale: s.label, config, query_id: q.id, ...diag });
      }
    }
    const inserts = source.find({}).sort({ ID: 1 }).limit(20).toArray();
    const ids = source
      .find({}, { _id: 0, ID: 1 })
      .sort({ ID: -1 })
      .limit(200)
      .toArray()
      .map((x) => x.ID);
    if (inserts.length !== 20 || ids.length !== 200) throw new Error("Write sample preparation failed");
    for (const config of ["A", "B", "C"]) {
      const copy = d.getCollection(writeNames[config]);
      if (config === "B") copy.createIndex(keysB, { name: "ix_uc3_key" });
      if (config === "C") copy.createIndex(keysC, { name: "ix_uc3_cover" });
      emit("WRITE_INDEXES", { scale: s.label, config, indexes: copy.getIndexes() });
      for (const kind of ["INSERT", "UPDATE"]) {
        const samples = [];
        for (let i = 0; i < 10; i++) {
          let affected;
          const start = performance.now();
          if (kind === "INSERT") {
            const batch = inserts.map((x, j) => {
              const out = { ...x, ID: s.rows + 10000000 + i * 20 + j };
              delete out._id;
              return out;
            });
            affected = Object.keys(copy.insertMany(batch).insertedIds).length;
          } else {
            affected = copy.updateMany({ ID: { $in: ids.slice(i * 20, (i + 1) * 20) } }, { $set: { OBJECT_NAME: "UC3_UPDATED_" + i } }).modifiedCount;
          }
          const elapsed_ms = performance.now() - start;
          if (affected !== 20) throw new Error("Write count mismatch: " + s.label + config + kind + i);
          samples.push({ iteration: i + 1, elapsed_ms, affected });
        }
        const sum = samples.reduce((x, y) => x + y.elapsed_ms, 0);
        emit("WRITE_RAW", { scale: s.label, config, kind, samples });
        emit("WRITE_SUMMARY", { scale: s.label, config, kind, rows: 200, ...BenchmarkCore.summarize(samples), rows_per_second: kind === "INSERT" ? 200000 / sum : null });
      }
      if (copy.countDocuments({}) !== s.rows + 200) throw new Error("Final write count wrong");
      emit("WRITE_FINAL", { scale: s.label, config, rows: s.rows + 200 });
    }
    if (source.countDocuments({}) !== s.rows) throw new Error("Source changed");
  }
  emit("RUN_COMPLETE", { status: "PASS" });
})();
