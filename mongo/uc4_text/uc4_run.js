/* Run from DBMS_Group2 root: mongosh --quiet --file mongo/uc4_text/uc4_run.js
   Creates only uc4_* copies. Seed is imported from the pinned JSONL first. */
load("mongo/benchmark/benchmark_core.js");
(() => {
  const d = db.getSiblingDB("dbms_ew_group02");
  const source = d.uc4_seed_10k;
  const run = "UC4-MONGO-" + new Date().toISOString();
  const emit = (section, data) => print(EJSON.stringify({ section, run_id: run, ...data }));
  const names = ["uc4_read_A", "uc4_read_C", "uc4_write_A", "uc4_write_C"];
  if (!d.version().startsWith("7.")) throw new Error("Expected MongoDB 7.x");
  if (source.countDocuments({}) !== 10000) throw new Error("UC4 source must have 10000 documents");
  for (const name of names) if (d.getCollectionNames().includes(name)) throw new Error("Existing UC4 copy: " + name);
  emit("ENVIRONMENT", { database: d.getName(), version: d.version(), rows: 10000, timing: "mongosh performance.now around find(...).toArray(), 2 warmups, 25 measured runs" });
  for (const name of names) {
    source.aggregate([{ $out: name }]).toArray();
    const c = d.getCollection(name);
    if (c.countDocuments({}) !== 10000 || c.getIndexes().length !== 1) throw new Error("Bad copy: " + name);
    emit("COPY_READY", { name, rows: 10000, indexes: c.getIndexes() });
  }
  const read = { A: d.uc4_read_A, C: d.uc4_read_C };
  const write = { A: d.uc4_write_A, C: d.uc4_write_C };
  for (const config of ["C"]) {
    for (const role of ["read", "write"]) {
      const c = role === "read" ? read[config] : write[config];
      const start = performance.now();
      const name = c.createIndex({ BODY: "text" }, { name: "ix_uc4_body_text", default_language: "english" });
      const elapsed_ms = performance.now() - start;
      const inv = BenchmarkCore.indexInventory(c);
      emit("INDEX_BUILD", { role, config, index_name: name, elapsed_ms, index_storage_bytes: inv.index_storage_bytes[name], index_options: c.getIndexes().find((x) => x.name === name) });
    }
  }
  for (const config of ["A", "C"]) emit("INDEX_INVENTORY", { config, ...BenchmarkCore.indexInventory(read[config]) });
  const queries = [
    ["K_HIGH", "election"],
    ["K_MED", "climate"],
    ["K_LOW", "bitcoin"],
    ["P_HIGH", "white house"],
    ["P_MED", "climate change"],
    ["P_LOW", "stock market"],
  ];
  const idsFor = (c, filter) =>
    c
      .find(filter, { _id: 0, DOC_ID: 1 })
      .toArray()
      .map((x) => x.DOC_ID)
      .sort((a, b) => a - b);
  for (const [query_id, term] of queries) {
    for (const config of ["A", "C"]) {
      const c = read[config];
      const filter = config === "A" ? { BODY: { $regex: term, $options: "i" } } : { $text: { $search: query_id.startsWith("P_") ? '"' + term + '"' : term } };
      const ids = idsFor(c, filter);
      if (ids.length === 0) throw new Error("Empty query " + query_id + config);
      emit("READ_IDS", { query_id, config, matched_rows: ids.length, doc_ids: ids });
      const samples = [];
      for (let i = -2; i < 25; i++) {
        const t = performance.now();
        const docs = c.find(filter, { _id: 0, DOC_ID: 1 }).toArray();
        const elapsed_ms = performance.now() - t;
        const got = docs.map((x) => x.DOC_ID).sort((a, b) => a - b);
        if (JSON.stringify(got) !== JSON.stringify(ids)) throw new Error("Read ID set changed: " + query_id + config);
        if (i >= 0) samples.push({ iteration: i + 1, elapsed_ms, matched_rows: docs.length });
      }
      emit("READ_RAW", { query_id, config, warmups: 2, samples });
      emit("READ_SUMMARY", { query_id, config, matched_rows: ids.length, ...BenchmarkCore.summarize(samples) });
      const plan = BenchmarkCore.explainFind(c, filter, { _id: 0, DOC_ID: 1 });
      if (plan.returned_rows !== ids.length) throw new Error("Plan result mismatch: " + query_id + config);
      emit("READ_PLAN", { query_id, config, ...plan });
    }
  }
  const insertSources = source.find({}).sort({ DOC_ID: 1 }).limit(20).toArray();
  const updateIds = source
    .find({}, { _id: 0, DOC_ID: 1 })
    .sort({ DOC_ID: -1 })
    .limit(200)
    .toArray()
    .map((x) => x.DOC_ID);
  const replacement = insertSources[0].BODY;
  if (insertSources.length !== 20 || updateIds.length !== 200) throw new Error("Write sample preparation failed");
  for (const config of ["A", "C"]) {
    const c = write[config];
    for (const kind of ["INSERT", "UPDATE"]) {
      const samples = [];
      for (let i = 0; i < 10; i++) {
        const batch = insertSources.map((doc, j) => ({ ...doc, _id: 1000000 + i * 20 + j, DOC_ID: 1000000 + i * 20 + j }));
        const filter = { DOC_ID: { $in: updateIds.slice(i * 20, (i + 1) * 20) } };
        const t = performance.now();
        const result = kind === "INSERT" ? c.insertMany(batch) : c.updateMany(filter, { $set: { BODY: replacement } });
        const elapsed_ms = performance.now() - t;
        const affected = kind === "INSERT" ? Object.keys(result.insertedIds).length : result.modifiedCount;
        if (affected !== 20) throw new Error("Write count mismatch: " + config + kind + i);
        samples.push({ iteration: i + 1, elapsed_ms, affected });
      }
      const total_ms = samples.reduce((x, y) => x + y.elapsed_ms, 0);
      emit("WRITE_RAW", { config, kind, samples });
      emit("WRITE_SUMMARY", { config, kind, rows: 200, ...BenchmarkCore.summarize(samples), rows_per_second: kind === "INSERT" ? 200000 / total_ms : null });
    }
    if (c.countDocuments({}) !== 10200) throw new Error("Write copy count mismatch");
  }
  const bitcoin = source.findOne({ BODY: /bitcoin/i });
  const target = write.C.findOne({ BODY: { $not: /bitcoin/i } }, { DOC_ID: 1 });
  if (!bitcoin || !target) throw new Error("Freshness payload unavailable");
  const t = performance.now();
  const result = write.C.updateOne({ _id: target._id }, { $set: { BODY: bitcoin.BODY } });
  let visible = false,
    polls = 0;
  while (!visible && performance.now() - t < 30000) {
    visible = write.C.find({ _id: target._id, $text: { $search: "bitcoin" } }, { _id: 1 })
      .limit(1)
      .hasNext();
    polls++;
    if (!visible) sleep(25);
  }
  emit("FRESHNESS", { config: "C", doc_id: target.DOC_ID, modified: result.modifiedCount, visible, polls, elapsed_ms: performance.now() - t });
  if (!visible) throw new Error("Mongo text freshness timeout");
  if (source.countDocuments({}) !== 10000) throw new Error("Seed changed");
  emit("RUN_COMPLETE", { status: "PASS" });
})();
