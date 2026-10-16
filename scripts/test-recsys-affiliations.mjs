import assert from 'node:assert/strict';
import fs from 'node:fs';
// An explicit fixture path permits isolated schema tests before the real export.
const data=JSON.parse(fs.readFileSync(process.argv[2] || new URL('../data/recsys-2026.json',import.meta.url)));
const reasonCodes=['source_unavailable','author_block_missing','extraction_unverified','no_institution_declared'];
function validate(d) {
  const orgs=new Set(d.organizations.map(o=>o.id));
  assert.equal(orgs.size,d.organizations.length);
  for (const [label, ids] of Object.entries(d.affiliationAliasMap)) {
    assert.ok(label && !label.includes('@') && ids.length);
    assert.ok(ids.every(id=>orgs.has(id)),'orphan alias');
  }
  for (const o of d.organizations) {
    assert.match(o.id,/^[a-z0-9-]+$/);
    assert.ok(['company','university','research','other'].includes(o.type));
    assert.ok(o.aliases.length && o.aliases.includes(o.name));
  }
  for (const p of d.papers) {
    if (p.affiliations.length) {
      assert.ok(!Object.hasOwn(p,'affiliationUnknownReason'),'known paper has unknown reason');
    } else {
      assert.ok(reasonCodes.includes(p.affiliationUnknownReason),'missing or invalid unknown reason');
      if (p.affiliationUnknownReason==='no_institution_declared') {
        assert.ok(p.nonInstitutionalAffiliations?.length,'independent reason needs evidence');
        assert.ok(p.nonInstitutionalAffiliations.every(a=>/^Independent(?: Researcher)?,|^Unaffiliated,/.test(a.quote) && /^https:\/\//.test(a.source) && a.locator));
      }
    }
    assert.equal(new Set(p.affiliations.map(a=>a.organization)).size,p.affiliations.length,'duplicate article-org');
    for (const a of p.affiliations) {
      assert.ok(orgs.has(a.organization),'unknown org');
      assert.match(a.source,/^https:\/\/(dl\.acm\.org\/doi\/(pdf|full)\/|arxiv\.org\/(pdf|html)\/|oars-workshop\.github\.io\/papers\/|drive\.google\.com\/uc\?export=download&id=14jd1670X1wyqdyDmsj0xsPJwx2MiuGyF$)/);
      assert.ok(a.quote && a.locator);
    }
  }
  assert.equal(d.stats.affiliationKnown,d.papers.filter(p=>p.affiliations.length).length);
  assert.equal(d.stats.affiliationUnknown,d.papers.filter(p=>!p.affiliations.length).length);
  assert.equal(d.stats.affiliationKnown+d.stats.affiliationUnknown,d.papers.length);
  assert.deepEqual(Object.keys(d.stats.affiliationUnknownReasons).sort(),[...reasonCodes].sort());
  for (const code of reasonCodes) {
    assert.equal(d.stats.affiliationUnknownReasons[code],d.papers.filter(p=>p.affiliationUnknownReason===code).length,'reason count: '+code);
  }
  assert.equal(Object.values(d.stats.affiliationUnknownReasons).reduce((n,v)=>n+v,0),d.stats.affiliationUnknown,'reason totals');
}
validate(data);
assert.equal(data.stats.reviewed,269);
assert.equal(data.stats.awaiting,0);
assert.equal(data.papers.find(p=>p.slug==='grip-profile-completion').affiliations.length,3);
for (const name of ['duplicate_pair','broken_org','unknown_count','missing_reason','invalid_reason','known_reason','reason_count','reason_distribution','missing_reason_bucket','invalid_reason_bucket','independent_evidence','orphan_alias']) {
  const d=structuredClone(data), p=d.papers.find(p=>p.affiliations.length);
  const unknown=d.papers.find(p=>!p.affiliations.length);
  assert.ok(unknown,'mutation fixture needs an unknown paper');
  if(name==='duplicate_pair')p.affiliations.push(p.affiliations[0]);
  if(name==='broken_org')p.affiliations[0].organization='nonexistent';
  if(name==='unknown_count')d.stats.affiliationUnknown=0;
  if(name==='missing_reason')delete unknown.affiliationUnknownReason;
  if(name==='invalid_reason')unknown.affiliationUnknownReason='not_a_reason';
  if(name==='known_reason')p.affiliationUnknownReason='extraction_unverified';
  if(name==='reason_count')d.stats.affiliationUnknownReasons[unknown.affiliationUnknownReason]++;
  if(name==='reason_distribution') {
    d.stats.affiliationUnknownReasons[unknown.affiliationUnknownReason]--;
    d.stats.affiliationUnknownReasons[reasonCodes.find(c=>c!==unknown.affiliationUnknownReason)]++;
  }
  if(name==='missing_reason_bucket')delete d.stats.affiliationUnknownReasons.source_unavailable;
  if(name==='invalid_reason_bucket')d.stats.affiliationUnknownReasons.not_a_reason=0;
  if(name==='independent_evidence')unknown.nonInstitutionalAffiliations=[];
  if(name==='orphan_alias')d.affiliationAliasMap[Object.keys(d.affiliationAliasMap)[0]]=['nonexistent'];
  assert.throws(()=>validate(d),undefined,name+' survived');
  console.log('MUTATION',name,'KILLED');
}
console.log('affiliation schema, dedup, multi-org, unknown reasons/totals and provenance PASS');
