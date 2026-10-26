/* Phase 7 UC6. Run from root: mongosh --quiet --file mongo/uc6_multikey/uc6_run.js
   Source must be imported from local_data/derived/uc6/parents_10k.jsonl. */
load('mongo/benchmark/benchmark_core.js');
(() => {
  const d = db.getSiblingDB('dbms_ew_group02');
  const source = d.uc6_seed_10k;
  const run = 'UC6-MONGO-' + new Date().toISOString();
  const emit = (section, data) => print(EJSON.stringify({ section, run_id: run, ...data }));
  const names = ['uc6_read_A','uc6_read_C','uc6_write_A','uc6_write_C'];
  if (!d.version().startsWith('7.')) throw new Error('Expected MongoDB 7.x');
  if (source.countDocuments({}) !== 10000) throw new Error('UC6 seed must have 10000 documents');
  for (const name of names) if (d.getCollectionNames().includes(name)) throw new Error('UC6 copy exists: ' + name);
  emit('ENVIRONMENT', { database: d.getName(), version: d.version(), parents: 10000,
    timing: 'performance.now around complete find.toArray; 2 warmups, 25 samples' });
  emit('ARRAY_LENGTHS', { distribution: source.aggregate([
    { $project: { length: { $size: '$tags' } } },
    { $group: { _id: '$length', count: { $sum: 1 } } }, { $sort: { _id: 1 } } ]).toArray() });
  for (const name of names) {
    source.aggregate([{ $out: name }]).toArray();
    const copy = d.getCollection(name);
    if (copy.countDocuments({}) !== 10000 || copy.getIndexes().length !== 1) throw new Error('Bad copy: ' + name);
    emit('COPY_READY', { name, parents: 10000, indexes: copy.getIndexes() });
  }
  const read = { A: d.uc6_read_A, C: d.uc6_read_C };
  const write = { A: d.uc6_write_A, C: d.uc6_write_C };
  for (const [role, copy] of [['Read', read.C], ['Write', write.C]]) {
    const start = performance.now();
    const index = copy.createIndex({ tags: 1 }, { name: 'ix_uc6_tags' });
    const elapsed_ms = performance.now() - start;
    const inventory = BenchmarkCore.indexInventory(copy);
    emit('INDEX_BUILD', { role, config: 'C', index, elapsed_ms,
      index_storage_bytes: inventory.index_storage_bytes[index], indexes: copy.getIndexes() });
  }
  for (const config of ['A','C']) emit('INDEX_INVENTORY', { config, ...BenchmarkCore.indexInventory(read[config]) });
  const queries = [
    { id: 'ONE_TABLE', tags: ['type:TABLE'] },
    { id: 'TWO_SYS_TABLE', tags: ['owner:SYS','type:TABLE'] },
    { id: 'ONE_TEMP_Y', tags: ['temporary:Y'] },
    { id: 'TWO_TABLE_TEMP_Y', tags: ['type:TABLE','temporary:Y'] }
  ];
  const idsFor = (collection, filter) => collection.find(filter, { _id:0, PARENT_ID:1 })
    .toArray().map(x => x.PARENT_ID).sort((a,b) => a-b);
  for (const query of queries) {
    const filter = query.tags.length === 1 ? { tags: query.tags[0] } : { tags: { $all: query.tags } };
    const expected = idsFor(source, filter);
    if (!expected.length) throw new Error('Empty query: ' + query.id);
    emit('QUERY_SELECTIVITY', { query_id: query.id, tags: query.tags,
      matched_parents: expected.length, selectivity: expected.length / 10000 });
    for (const config of ['A','C']) {
      const copy = read[config];
      const ids = idsFor(copy, filter);
      if (JSON.stringify(ids) !== JSON.stringify(expected)) throw new Error('Copy result mismatch: ' + query.id+config);
      emit('READ_IDS', { query_id: query.id, config, matched_parents: ids.length, parent_ids: ids });
      const samples = [];
      for (let i=-2; i<25; i++) {
        const start = performance.now();
        const rows = copy.find(filter, { _id:0, PARENT_ID:1 }).toArray();
        const elapsed_ms = performance.now() - start;
        const got = rows.map(x => x.PARENT_ID).sort((a,b) => a-b);
        if (JSON.stringify(got) !== JSON.stringify(expected)) throw new Error('Timed result mismatch: ' + query.id+config);
        if (i>=0) samples.push({ iteration:i+1, elapsed_ms, matched_parents:rows.length });
      }
      emit('READ_RAW', { query_id: query.id, config, warmups:2, samples });
      emit('READ_SUMMARY', { query_id: query.id, config, matched_parents:ids.length,
        ...BenchmarkCore.summarize(samples) });
      const plan = BenchmarkCore.explainFind(copy, filter, { _id:0, PARENT_ID:1 });
      if (plan.returned_rows !== expected.length) throw new Error('Plan mismatch: ' + query.id+config);
      emit('READ_PLAN', { query_id: query.id, config, ...plan });
    }
  }
  const inserts = source.find({}).sort({ PARENT_ID:1 }).limit(20).toArray();
  const updateIds = source.find({}, { _id:0, PARENT_ID:1 }).sort({ PARENT_ID:-1 }).limit(200)
    .toArray().map(x => x.PARENT_ID);
  if (inserts.length !== 20 || updateIds.length !== 200) throw new Error('Write selection failed');
  for (const config of ['A','C']) {
    const copy = write[config];
    for (const kind of ['INSERT','ADD_TAG']) {
      const samples = [];
      for (let i=0; i<10; i++) {
        const batch = inserts.map((x,j) => ({ ...x, _id:1000000+i*20+j, PARENT_ID:1000000+i*20+j }));
        const targetIds = updateIds.slice(i*20,(i+1)*20);
        const start = performance.now();
        const result = kind === 'INSERT' ? copy.insertMany(batch) :
          copy.updateMany({ PARENT_ID: { $in: targetIds } }, { $addToSet: { tags:'probe:added' } });
        const elapsed_ms = performance.now() - start;
        const affected = kind === 'INSERT' ? Object.keys(result.insertedIds).length : result.modifiedCount;
        if (affected !== 20) throw new Error('Write count mismatch: ' + kind+config+i);
        samples.push({ iteration:i+1, elapsed_ms, affected });
      }
      const sum = samples.reduce((x,y) => x+y.elapsed_ms,0);
      emit('WRITE_RAW', { config, kind, samples });
      emit('WRITE_SUMMARY', { config, kind, rows:200,
        ...BenchmarkCore.summarize(samples), rows_per_second:kind==='INSERT' ? 200000/sum : null });
    }
    if (copy.countDocuments({}) !== 10200 ||
        copy.countDocuments({ PARENT_ID:{ $in:updateIds }, tags:'probe:added' }) !== 200)
      throw new Error('Final write state mismatch: ' + config);
  }
  if (source.countDocuments({}) !== 10000) throw new Error('Seed changed');
  emit('RUN_COMPLETE', { status:'PASS' });
})();
