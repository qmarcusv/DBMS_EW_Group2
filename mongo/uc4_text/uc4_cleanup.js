/* Explicit UC4 cleanup; save all UC4 evidence first. */
(() => {
  const d = db.getSiblingDB('dbms_ew_group02');
  for (const name of ['uc4_read_A','uc4_read_C','uc4_write_A','uc4_write_C','uc4_seed_10k']) {
    if (d.getCollectionNames().includes(name)) {
      d.getCollection(name).drop();
      print(EJSON.stringify({ section: 'UC4_CLEANUP', collection: name, dropped: true }));
    }
  }
})();
