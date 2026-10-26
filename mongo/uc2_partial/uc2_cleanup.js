/* Only after saving UC2 JSONL. Drops exactly eight UC2 copies. */
load('mongo/benchmark/benchmark_core.js');
(() => {
  const d = db.getSiblingDB('dbms_ew_group02');
  const names = ['100K','1000K'].flatMap(s => ['uc2_bench_'+s,
    ...['A','B','C'].map(c => 'uc2_write_'+c+'_'+s)]);
  for (const name of names) if (d.getCollectionNames().includes(name)) {
    const c = d.getCollection(name);
    print(EJSON.stringify({section:'COPY_DROPPED',name,rows_before:c.countDocuments({}),
      dropped:BenchmarkCore.dropDisposable(c)}));
  }
  print(EJSON.stringify({section:'AFTER_CLEANUP',remaining:names.filter(n=>d.getCollectionNames().includes(n)),
    source_100k:d.big_table_100k.countDocuments({}),source_1m:d.big_table_1000K.countDocuments({})}));
})();
