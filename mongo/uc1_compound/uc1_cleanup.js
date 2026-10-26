/* Run only after saving benchmark JSONL and plan evidence.
   Drops exactly four disposable UC1 collections, never big_table_100k. */
load('mongo/benchmark/benchmark_core.js');
(() => {
  const auditDb = db.getSiblingDB('dbms_ew_group02');
  const names = ['uc1_bench_100K','uc1_write_A_100K',
    'uc1_write_B_100K','uc1_write_C_100K'];
  for (const name of names) {
    if (auditDb.getCollectionNames().includes(name)) {
      const collection = auditDb.getCollection(name);
      print(EJSON.stringify({section:'COPY_DROPPED',name,
        rows_before:collection.countDocuments({}),
        dropped:BenchmarkCore.dropDisposable(collection)}));
    }
  }
  print(EJSON.stringify({section:'AFTER_CLEANUP',
    reference_rows:auditDb.getCollection('big_table_100k').countDocuments({}),
    remaining:names.filter(n=>auditDb.getCollectionNames().includes(n))}));
})();
