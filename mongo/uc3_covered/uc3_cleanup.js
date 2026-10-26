/* Drop only UC3 disposable collections after raw output is saved. */
load('mongo/benchmark/benchmark_core.js');
(() => {
  const d = db.getSiblingDB('dbms_ew_group02');
  for (const scale of ['100K', '1000K']) {
    for (const name of ['uc3_bench_' + scale,
      ...['A', 'B', 'C'].map(c => 'uc3_write_' + c + '_' + scale)]) {
      if (d.getCollectionNames().includes(name)) {
        BenchmarkCore.dropDisposable(d.getCollection(name));
        print(EJSON.stringify({ section: 'UC3_CLEANUP', name }));
      }
    }
  }
})();
