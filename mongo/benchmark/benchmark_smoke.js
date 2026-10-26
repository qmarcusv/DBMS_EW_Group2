/*
Run from DBMS_Group2 workspace root:
  mongosh "mongodb://localhost:27017/dbms_ew_group02" --file ".\mongo\benchmark\benchmark_smoke.js"
Read-only infrastructure smoke. Output is one EJSON object per line.
*/
load("mongo/benchmark/benchmark_core.js");
(() => {
  const auditDb = db.getSiblingDB("dbms_ew_group02");
  if (!auditDb.getCollectionNames().includes("big_table_10K")) throw new Error("Exact-case 10K reference collection is missing");
  const collection = auditDb.getCollection("big_table_10K");
  const filter = {};
  const projection = { _id: 0, ID: 1, OBJECT_ID: 1, OBJECT_NAME: 1 };
  const runId = "P2-" + new Date().toISOString() + "-" + Math.floor(Math.random() * 1000000);
  const result = BenchmarkCore.runFind({ collection, filter, projection, warmups: 2, repetitions: 7, expectedCount: 10000, runId, queryId: "P2_SMOKE_FULL_10K", configuration: "SMOKE" });
  result.dataset_row_count = 10000;
  const inventory = BenchmarkCore.indexInventory(collection);
  result.index_storage_bytes = inventory.index_storage_bytes;
  const diagnostic = BenchmarkCore.explainFind(collection, filter, projection, null);
  result.total_keys_examined = diagnostic.total_keys_examined;
  result.total_docs_examined = diagnostic.total_docs_examined;
  result.query_plan_reference = "PLAN section in this transcript";

  print(EJSON.stringify({ section: "RAW_SAMPLES", run_id: runId, samples: result.raw_samples }));
  print(EJSON.stringify({ section: "BENCHMARK_SUMMARY", ...result, raw_samples: undefined }));
  print(EJSON.stringify({ section: "INDEX_INVENTORY", run_id: runId, collection: collection.getName(), ...inventory }));
  print(EJSON.stringify({ section: "PLAN", run_id: runId, query_id: result.query_id, ...diagnostic }));
  if (result.correctness_status !== "PASS" || diagnostic.returned_rows !== 10000) throw new Error("Smoke correctness failed; inspect raw samples and explain");
})();
