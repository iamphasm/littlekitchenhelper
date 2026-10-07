/// <reference path="../pb_data/types.d.ts" />
// Assign sequential numeric member ids (1, 2, 3, ...) to new family members.
onRecordCreate((e) => {
  const row = new DynamicModel({ top: 0 })
  $app.db().newQuery("SELECT COALESCE(MAX(memberNo), 0) AS top FROM users").one(row)
  e.record.set("memberNo", row.top + 1)
  e.next()
}, "users")
