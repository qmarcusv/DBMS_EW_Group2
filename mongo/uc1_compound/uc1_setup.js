/* Run from DBMS_Group2 root with mongosh --file. Creates four disposable copies.
   Never runs when a target already exists; never changes big_table_100k. */
(() => {
  const auditDb = db.getSiblingDB("dbms_ew_group02");
  const sourceName = "big_table_100k";
  const names = ["uc1_bench_100K", "uc1_write_A_100K", "uc1_write_B_100K", "uc1_write_C_100K"];
  const existing = auditDb.getCollectionNames();
  if (auditDb.version().split(".")[0] !== "7") throw new Error("Expected MongoDB 7.x; inspect environment");
  if (!existing.includes(sourceName)) throw new Error("Exact-case source missing");
  for (const name of names) {
    if (existing.includes(name)) throw new Error("Copy already exists: " + name);
  }
  const source = auditDb.getCollection(sourceName);
  if (source.countDocuments({}) !== 100000) throw new Error("Source row count is not 100000");
  print(EJSON.stringify({ section: "SOURCE_INDEXES", collection: sourceName, indexes: source.getIndexes() }));

  for (const name of names) {
    // New $out destination starts with _id_ only; verify rather than assume.
    source.aggregate([{ $out: name }]).toArray();
    const copy = auditDb.getCollection(name);
    const indexes = copy.getIndexes();
    const check = copy.aggregate([{ $group: { _id: null, rows: { $sum: 1 }, id_sum: { $sum: "$ID" }, object_id_sum: { $sum: "$OBJECT_ID" } } }]).toArray()[0];
    print(EJSON.stringify({ section: "COPY_PARITY", name, rows: check.rows, id_sum: check.id_sum, object_id_sum: check.object_id_sum, indexes }));
    if (Number(check.rows) !== 100000 || Number(check.id_sum) !== 5000050000 || indexes.length !== 1 || indexes[0].name !== "_id_") throw new Error("Copy verification failed: " + name);
  }
  print(EJSON.stringify({ section: "COPY_READY", names, note: "Four 100K copies; each has only mandatory _id_ index." }));
})();
