/*
Phase 1 read-only inventory. Run in mongosh against the intended local server:
  load('mongo/phase1_verify.js')
or:
  mongosh 'mongodb://127.0.0.1:27017/dbms_ew_group02' --file mongo/phase1_verify.js

No collection/index creation, mutation, deletion, or benchmark execution.
Exact scans cover 10K, 100K, and 1000K. The 15000K collection is metadata-only.
*/
(() => {
  const auditDb = db.getSiblingDB('dbms_ew_group02');
  const targets = [
    { scale: '10K', name: 'big_table_10K', exactScan: true },
    { scale: '100K', name: 'big_table_100k', exactScan: true },
    { scale: '1000K', name: 'big_table_1000K', exactScan: true },
    { scale: '15000K', name: 'big_table_15000K', exactScan: false }
  ];

  function emit(section, value) {
    print(EJSON.stringify({ section, ...value }));
  }
  function errorText(error) {
    return error && error.message ? error.message : String(error);
  }

  emit('SERVER', {
    database: auditDb.getName(),
    serverVersion: auditDb.version(),
    mongoshVersion: 'Run mongosh --version and record it with this output'
  });
  try {
    const status = auditDb.adminCommand({ serverStatus: 1 });
    emit('STORAGE_ENGINE', {
      name: status.storageEngine && status.storageEngine.name,
      persistent: status.storageEngine && status.storageEngine.persistent
    });
  } catch (error) {
    emit('STORAGE_ENGINE', { status: 'NOT_VERIFIED', error: errorText(error) });
  }

  let observedNames;
  try {
    observedNames = auditDb.getCollectionNames();
    emit('COLLECTION_NAMES', { names: observedNames.sort() });
  } catch (error) {
    emit('COLLECTION_NAMES', { status: 'NOT_VERIFIED', error: errorText(error) });
    return;
  }

  for (const target of targets) {
    const { scale, name, exactScan } = target;
    const exists = observedNames.includes(name);
    emit('TARGET_EXISTENCE', { scale, expectedName: name, exists });
    if (!exists) {
      emit('SCAN_STATUS', { scale, status: 'NOT_EXECUTED: collection missing' });
      continue;
    }

    const collection = auditDb.getCollection(name);
    try {
      emit('INDEXES', { scale, name, indexes: collection.getIndexes() });
    } catch (error) {
      emit('INDEXES', { scale, name, status: 'NOT_VERIFIED', error: errorText(error) });
    }
    try {
      const stats = collection.stats({ scale: 1 });
      emit('COLLECTION_STATS', {
        scale, name, dataSizeBytes: stats.size,
        storageSizeBytes: stats.storageSize, indexSizesBytes: stats.indexSizes
      });
    } catch (error) {
      emit('COLLECTION_STATS', { scale, name, status: 'NOT_VERIFIED', error: errorText(error) });
    }

    if (!exactScan) {
      try {
        emit('METADATA_COUNT', {
          scale, name, estimatedDocuments: collection.estimatedDocumentCount(),
          status: 'ESTIMATE_ONLY; optional 15M exact scan skipped'
        });
      } catch (error) {
        emit('METADATA_COUNT', { scale, name, status: 'NOT_VERIFIED', error: errorText(error) });
      }
      continue;
    }

    try {
      emit('PREDICATE_COUNTS', {
        scale, name,
        totalDocuments: collection.countDocuments({}),
        objectId100To500: collection.countDocuments({ OBJECT_ID: { $gte: 100, $lte: 500 } }),
        sysTable: collection.countDocuments({ OWNER: 'SYS', OBJECT_TYPE: 'TABLE' }),
        temporaryY: collection.countDocuments({ TEMPORARY: 'Y' })
      });
    } catch (error) {
      emit('PREDICATE_COUNTS', { scale, name, status: 'NOT_VERIFIED', error: errorText(error) });
    }

    // Aggregation $type distinguishes numeric BSON types from null and missing.
    try {
      const typeGroups = collection.aggregate([
        { $project: {
          idType: { $type: '$ID' },
          objectIdType: { $type: '$OBJECT_ID' },
          ownerType: { $type: '$OWNER' },
          objectTypeType: { $type: '$OBJECT_TYPE' },
          temporaryType: { $type: '$TEMPORARY' }
        } },
        { $group: {
          _id: {
            ID: '$idType', OBJECT_ID: '$objectIdType',
            OWNER: '$ownerType', OBJECT_TYPE: '$objectTypeType',
            TEMPORARY: '$temporaryType'
          },
          documents: { $sum: 1 }
        } },
        { $sort: { documents: -1 } }
      ], { allowDiskUse: false }).toArray();
      emit('FIELD_TYPES', { scale, name, groups: typeGroups });
    } catch (error) {
      emit('FIELD_TYPES', { scale, name, status: 'NOT_VERIFIED', error: errorText(error) });
    }

    try {
      const samples = collection.find(
        { ID: { $in: [1, 5000, 10000, 100000, 1000000] } },
        { _id: 0, ID: 1, OBJECT_ID: 1, OWNER: 1, OBJECT_TYPE: 1, TEMPORARY: 1 }
      ).sort({ ID: 1 }).toArray();
      emit('SAMPLE_IDS', { scale, name, rows: samples });
    } catch (error) {
      emit('SAMPLE_IDS', { scale, name, status: 'NOT_VERIFIED', error: errorText(error) });
    }
  }

  emit('INDEX_CREATE_PERMISSION', {
    status: 'NOT_VERIFIED_READ_ONLY',
    note: 'Phase 2 must check permissions on disposable benchmark copies before DDL.'
  });
})();
