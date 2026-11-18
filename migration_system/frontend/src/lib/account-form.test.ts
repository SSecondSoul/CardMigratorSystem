import test from 'node:test'
import assert from 'node:assert/strict'
import {validateAccountDraft} from './account-form.ts'
const draft={username:'zhangsan_01',display_name:'张三',password:'Random-test-secret-42',role:'user'}
test('account form accepts backend-supported names, roles and passwords without extra complexity rules',()=>{
  for(const username of ['abc','User.01','test-user_2','A'.repeat(64)])assert.equal(validateAccountDraft({...draft,username}).username,'')
  for(const role of ['user','admin'])assert.equal(validateAccountDraft({...draft,role}).role,'')
  for(const password of ['a'.repeat(12),'x'.repeat(128),'文'.repeat(12),'😀'.repeat(12)])assert.equal(validateAccountDraft({...draft,password}).password,'')
  assert.deepEqual(Object.values(validateAccountDraft(draft)),['','','',''])
})
test('invalid account fields have actionable Chinese errors before submission',()=>{
  for(const username of ['','ab','1user','张三','a user','abc\n','a'.repeat(65)])assert.ok(validateAccountDraft({...draft,username}).username)
  for(const password of ['','short','x'.repeat(129)])assert.ok(validateAccountDraft({...draft,password}).password)
  for(const display_name of ['','   ','文'.repeat(121)])assert.ok(validateAccountDraft({...draft,display_name}).display_name)
  assert.ok(validateAccountDraft({...draft,role:'owner'}).role)
  assert.equal(validateAccountDraft({...draft,display_name:' 张三 '}).display_name,'')
})
