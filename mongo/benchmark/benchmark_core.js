/*
Mongosh 2.13-compatible helpers. From the DBMS_Group2 workspace root:
  load('mongo/benchmark/benchmark_core.js')
No Node package, require(), or external runner is used.
The read helper consumes the entire cursor inside every timed interval.
*/
var BenchmarkCore = (() => {
  const database = db.getSiblingDB("dbms_ew_group02");

  function assertDisposable(collection) {
    const name = collection.getName();
    if (collection.getDB().getName() !== "dbms_ew_group02" || !/^(uc[1-6]_|bench_)[A-Za-z0-9_]+$/i.test(name)) {
      throw new Error("Writes require a named disposable UC/BENCH collection in dbms_ew_group02: " + name);
    }
  }

  function percentile(sorted, p) {
    if (!sorted.length) throw new Error("At least one sample is required");
    const position = (sorted.length - 1) * p;
    const lower = Math.floor(position);
    const fraction = position - lower;
    return sorted[lower] + fraction * (sorted[Math.ceil(position)] - sorted[lower]);
  }

  function summarize(samples) {
    const sorted = samples.map((s) => s.elapsed_ms).sort((a, b) => a - b);
    return {
      repetition_count: sorted.length,
      query_median_ms: percentile(sorted, 0.5),
      query_p95_ms: percentile(sorted, 0.95),
      raw_timings_ms: samples.map((s) => s.elapsed_ms),
    };
  }

  function indexInventory(collection) {
    const stats = collection.stats({ scale: 1 });
    return {
      indexes: collection.getIndexes(),
      index_storage_bytes: stats.indexSizes,
      collection_storage_bytes: stats.storageSize,
      logical_data_bytes: stats.size,
    };
  }

  function runFind(options) {
    const { collection, filter = {}, projection = {}, sort = null, warmups = 2, repetitions = 25, expectedCount, expectedIdSum = null, runId, queryId, configuration = "SMOKE", phase = "PHASE2", useCase = "SMOKE" } = options;
    if (!collection || !Number.isInteger(warmups) || warmups < 0 || !Number.isInteger(repetitions) || repetitions < 1 || repetitions > 1000 || !Number.isInteger(expectedCount) || expectedCount < 0) {
      throw new Error("Invalid collection, iteration count, or expectedCount");
    }
    const raw = [];
    let baselineIdSum = null;
    for (let iteration = -warmups; iteration < repetitions; iteration++) {
      let count = 0;
      let idSum = 0;
      let missingId = 0;
      const started = Date.now();
      let cursor = collection.find(filter, projection);
      if (sort) cursor = cursor.sort(sort);
      cursor.forEach((doc) => {
        count++;
        if (Number.isSafeInteger(doc.ID)) idSum += doc.ID;
        else missingId++;
      });
      const elapsed = Date.now() - started;
      if (baselineIdSum === null) baselineIdSum = idSum;
      if (iteration >= 0) {
        const correct = count === expectedCount && missingId === 0 && idSum === baselineIdSum && (expectedIdSum === null || idSum === expectedIdSum);
        raw.push({ iteration: iteration + 1, elapsed_ms: elapsed, returned_rows: count, id_sum: idSum, missing_id: missingId, correctness_status: correct ? "PASS" : "FAIL" });
      }
    }
    const summary = summarize(raw);
    return {
      run_id: runId,
      timestamp: new Date().toISOString(),
      phase,
      use_case: useCase,
      dbms: "MONGODB",
      server_version: database.version(),
      dataset: collection.getName(),
      query_id: queryId,
      configuration,
      warmup_count: warmups,
      ...summary,
      timing_method: "mongosh Date.now; full cursor consumption; 1 ms resolution",
      returned_rows: raw[0].returned_rows,
      id_sum: raw[0].id_sum,
      correctness_status: raw.every((s) => s.correctness_status === "PASS") ? "PASS" : "FAIL",
      raw_samples: raw,
      logical_reads: null,
      total_keys_examined: null,
      total_docs_examined: null,
      index_build_ms: null,
      insert_rows_per_second: null,
      update_median_ms: null,
      query_plan_reference: null,
    };
  }

  function explainFind(collection, filter, projection, sort) {
    let cursor = collection.find(filter, projection);
    if (sort) cursor = cursor.sort(sort);
    const plan = cursor.explain("executionStats");
    const stats = plan.executionStats || {};
    return {
      total_keys_examined: stats.totalKeysExamined ?? null,
      total_docs_examined: stats.totalDocsExamined ?? null,
      returned_rows: stats.nReturned ?? null,
      plan,
    };
  }

  // Future UC scripts call these only on independent disposable collections.
  function timeIndexBuild(collection, keys, options) {
    assertDisposable(collection);
    const started = Date.now();
    const indexName = collection.createIndex(keys, options);
    return { index_name: indexName, index_build_ms: Date.now() - started, index_storage_bytes: indexInventory(collection).index_storage_bytes[indexName] ?? null };
  }

  function timeInsert(collection, documents) {
    assertDisposable(collection);
    if (!Array.isArray(documents) || !documents.length) throw new Error("Nonempty document batch required");
    const started = Date.now();
    const result = collection.insertMany(documents);
    const elapsed = Date.now() - started;
    const inserted = Object.keys(result.insertedIds).length;
    return { inserted_rows: inserted, insert_elapsed_ms: elapsed, insert_rows_per_second: elapsed > 0 ? (inserted * 1000) / elapsed : null };
  }

  function timeUpdate(collection, filter, update) {
    assertDisposable(collection);
    const started = Date.now();
    const result = collection.updateMany(filter, update);
    return { matched_rows: result.matchedCount, modified_rows: result.modifiedCount, update_elapsed_ms: Date.now() - started };
  }

  function dropDisposable(collection) {
    assertDisposable(collection);
    return collection.drop();
  }

  return { database, percentile, summarize, indexInventory, runFind, explainFind, timeIndexBuild, timeInsert, timeUpdate, dropDisposable };
})();
