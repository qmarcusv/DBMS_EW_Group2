/* Phase 4 UC2, mongosh --file from DBMS_Group2 root. Creates only uc2_* copies.
   100K and 1M. Refuses existing copies. Save JSONL before cleanup. */
load("mongo/benchmark/benchmark_core.js");
(() => {
  const d = db.getSiblingDB("dbms_ew_group02");
  const run = "UC2-" + new Date().toISOString();
  const emit = (section, x) => print(EJSON.stringify({ section, run_id: run, ...x }));
  const scales = [
    { label: "100K", source: "big_table_100k", rows: 100000, y: 254, n: 99746 },
    { label: "1000K", source: "big_table_1000K", rows: 1000000, y: 2405, n: 997595 },
  ];
  const keys = { OBJECT_TYPE: 1, OBJECT_ID: 1, TEMPORARY: 1 };
  const projection = { _id: 0, OBJECT_TYPE: 1, OBJECT_ID: 1, TEMPORARY: 1 };
  const values = ["Y", "N"];
  const copies = scales.flatMap((s) => ["uc2_bench_" + s.label, ...["A", "B", "C"].map((c) => "uc2_write_" + c + "_" + s.label)]);
  const existing = d.getCollectionNames();
  if (d.version().split(".")[0] !== "7") throw new Error("MongoDB 7.x required");
  for (const name of copies) if (existing.includes(name)) throw new Error("UC2 copy already exists: " + name);
  for (const s of scales) {
    if (!existing.includes(s.source)) throw new Error("Source missing: " + s.source);
    const source = d.getCollection(s.source);
    if (source.countDocuments({}) !== s.rows || source.countDocuments({ TEMPORARY: "Y" }) !== s.y || source.countDocuments({ TEMPORARY: "N" }) !== s.n) throw new Error("Source parity failed: " + s.source);
  }
  emit("ENVIRONMENT", { database: d.getName(), version: d.version(), scales });

  for (const s of scales) {
    const source = d.getCollection(s.source);
    const read = d.getCollection("uc2_bench_" + s.label);
    const writeNames = Object.fromEntries(["A", "B", "C"].map((c) => [c, "uc2_write_" + c + "_" + s.label]));
    for (const name of [read.getName(), ...Object.values(writeNames)]) {
      source.aggregate([{ $out: name }]).toArray();
      const copy = d.getCollection(name);
      const indexes = copy.getIndexes().map((i) => i.name);
      if (copy.countDocuments({}) !== s.rows || JSON.stringify(indexes) !== '["_id_"]') throw new Error("Copy parity/index failure: " + name);
      emit("COPY_READY", { scale: s.label, name, rows: s.rows, indexes });
    }
    const expected = {};
    for (const value of values) {
      const filter = { TEMPORARY: value, OBJECT_TYPE: "TABLE", OBJECT_ID: { $gte: 1, $lte: 10000 } };
      const docs = source.find(filter, projection).toArray();
      const sum = docs.reduce((a, x) => a + x.OBJECT_ID, 0);
      if (!docs.length) throw new Error("Empty workload: " + s.label + value);
      expected[value] = { filter, count: docs.length, sum };
      emit("QUERY_SELECTIVITY", { scale: s.label, value, rows: docs.length, selectivity: docs.length / s.rows });
    }
    for (const config of ["A", "B", "C"]) {
      if (config === "B") emit("INDEX_BUILD", { scale: s.label, config, ...BenchmarkCore.timeIndexBuild(read, keys, { name: "ix_uc2_full" }) });
      if (config === "C") {
        read.dropIndex("ix_uc2_full");
        emit("INDEX_BUILD", { scale: s.label, config, ...BenchmarkCore.timeIndexBuild(read, keys, { name: "ix_uc2_partial", partialFilterExpression: { TEMPORARY: "Y" } }) });
      }
      emit("INDEX_INVENTORY", { scale: s.label, config, indexes: read.getIndexes(), storage: BenchmarkCore.indexInventory(read).index_storage_bytes });
      for (const value of values) {
        const q = expected[value];
        const samples = [];
        for (let i = -2; i < 25; i++) {
          let count = 0,
            sum = 0;
          const start = performance.now();
          read.find(q.filter, projection).forEach((x) => {
            count++;
            sum += x.OBJECT_ID;
          });
          const elapsed_ms = performance.now() - start;
          if (count !== q.count || sum !== q.sum) throw new Error("Read result mismatch");
          if (i >= 0) samples.push({ iteration: i + 1, elapsed_ms, count, object_id_sum: sum });
        }
        emit("READ_RAW", { scale: s.label, config, value, samples });
        emit("READ_SUMMARY", { scale: s.label, config, value, count: q.count, selectivity: q.count / s.rows, warmups: 2, ...BenchmarkCore.summarize(samples) });
        const diagnostic = BenchmarkCore.explainFind(read, q.filter, projection);
        if (diagnostic.returned_rows !== q.count) throw new Error("Explain count mismatch");
        emit("READ_PLAN", { scale: s.label, config, value, ...diagnostic });
      }
    }

    const insertSamples = Object.fromEntries(values.map((v) => [v, source.find({ TEMPORARY: v }).sort({ ID: 1 }).limit(20).toArray()]));
    const updateIds = Object.fromEntries(
      values.map((v) => [
        v,
        source
          .find({ TEMPORARY: v }, { _id: 0, ID: 1 })
          .sort({ ID: -1 })
          .limit(200)
          .toArray()
          .map((x) => x.ID),
      ]),
    );
    for (const v of values) if (insertSamples[v].length !== 20 || updateIds[v].length !== 200) throw new Error("Insufficient write samples: " + s.label + v);
    for (const config of ["A", "B", "C"]) {
      const copy = d.getCollection(writeNames[config]);
      if (config === "B") copy.createIndex(keys, { name: "ix_uc2_full" });
      if (config === "C") copy.createIndex(keys, { name: "ix_uc2_partial", partialFilterExpression: { TEMPORARY: "Y" } });
      emit("WRITE_INDEXES", { scale: s.label, config, indexes: copy.getIndexes() });
      for (const kind of ["INSERT_N", "INSERT_Y", "N_TO_Y", "Y_TO_N"]) {
        const raw = [];
        for (let i = 0; i < 10; i++) {
          let elapsed_ms, affected;
          if (kind.startsWith("INSERT")) {
            const v = kind.slice(-1);
            const docs = insertSamples[v].map((x, j) => {
              const out = { ...x, ID: s.rows + 10000000 + (v === "Y" ? 1000 : 0) + i * 20 + j };
              delete out._id;
              return out;
            });
            const start = performance.now();
            const result = copy.insertMany(docs);
            elapsed_ms = performance.now() - start;
            affected = Object.keys(result.insertedIds).length;
          } else {
            const from = kind[0],
              to = kind.slice(-1);
            const ids = updateIds[from].slice(i * 20, (i + 1) * 20);
            const start = performance.now();
            const result = copy.updateMany({ ID: { $in: ids }, TEMPORARY: from }, { $set: { TEMPORARY: to } });
            elapsed_ms = performance.now() - start;
            affected = result.modifiedCount;
          }
          if (affected !== 20) throw new Error("Write count mismatch " + s.label + config + kind + i + ": " + affected);
          raw.push({ iteration: i + 1, elapsed_ms, affected });
        }
        emit("WRITE_RAW", { scale: s.label, config, kind, samples: raw });
        const sumMs = raw.reduce((a, x) => a + x.elapsed_ms, 0);
        emit("WRITE_SUMMARY", { scale: s.label, config, kind, batches: 10, rows: 200, ...BenchmarkCore.summarize(raw), rows_per_second: 200000 / sumMs });
      }
      const rows = copy.countDocuments({});
      if (rows !== s.rows + 400) throw new Error("Write final rows mismatch");
      emit("WRITE_FINAL", { scale: s.label, config, rows });
    }
    if (source.countDocuments({}) !== s.rows) throw new Error("Source count changed");
  }
  emit("RUN_COMPLETE", { status: "PASS" });
})();
