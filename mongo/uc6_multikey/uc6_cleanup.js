/* Explicit cleanup only after UC6 results have been saved and verified. */
(() => {
  const d = db.getSiblingDB('dbms_ew_group02');
  for (const name of ['uc6_read_A','uc6_read_C','uc6_write_A','uc6_write_C','uc6_seed_10k']) {
    if (d.getCollectionNames().includes(name)) {
      d.getCollection(name).drop();
      print(EJSON.stringify({ section:'UC6_CLEANUP', collection:name, dropped:true }));
    }
  }
})();
