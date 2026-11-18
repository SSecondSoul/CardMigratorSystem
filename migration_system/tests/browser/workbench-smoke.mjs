// Only local disposable Flask test server; never connects to a user's API or model.
import {createRequire} from 'node:module'
const require=createRequire(new URL('../../browser/package.json',import.meta.url))
const puppeteer=require('puppeteer-core')
import fs from 'node:fs'
import assert from 'node:assert/strict'
const config=JSON.parse(fs.readFileSync(0,'utf8'))
const browser=await puppeteer.launch({executablePath:config.executable,headless:true})
try{
 const page=await browser.newPage(),errors=[],submissions=[],writeHeaders=[]
 page.on('pageerror',e=>errors.push(e.message))
 page.on('request',r=>{if(r.method()==='POST'){writeHeaders.push(r.headers());if(new URL(r.url()).pathname==='/api/v1/migrations')submissions.push(JSON.parse(r.postData()))}})
 await page.goto(config.url,{waitUntil:'networkidle0'})
 await page.click('.cm-new-task')
 await page.waitForSelector('.cm-dialog[open]')
 await page.locator('.cm-dialog textarea').fill(config.source)
 assert.equal((await page.$$('.cm-dialog input[type=password]')).length,0)
 assert.equal((await page.$$('.cm-dialog input[type=checkbox]')).length,0)
 assert.equal(await page.$eval('.cm-dialog input[aria-label="迁移策略"]',e=>e.readOnly),true)
 await page.waitForFunction(()=>document.querySelector('.cm-dialog button[type=submit]')?.disabled===false)
 await page.click('.cm-dialog button[type=submit]')
 await page.waitForFunction(()=>document.querySelector('.cm-workbench')?.textContent.includes('排队'),{timeout:10000})
 assert.equal(submissions.length,1)
 assert.equal(submissions[0].strategy,'ssm');assert.equal(submissions[0].trusted_source,true);assert.equal(submissions[0].confirm_model_calls,true)
 assert.ok(writeHeaders.every(h=>!h['x-cardmig-token']&&h['x-cardmig-csrf']?.length===43))
 assert.equal(await page.evaluate(()=>document.cookie.includes('cardmig_session_')),false)
 await page.reload({waitUntil:'networkidle0'})
 await page.click('.cm-new-task');await page.waitForSelector('.cm-dialog[open]')
 await page.locator('.cm-dialog textarea').fill(config.source)
 await page.waitForFunction(()=>document.querySelector('.cm-dialog button[type=submit]')?.disabled===false)
 assert.equal(submissions.length,1,'refreshing a session must never resubmit a job')
 await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('.cm-dialog'))
 page.on('dialog',dialog=>dialog.accept())
 await page.click('.cm-report-footer button')
 await page.waitForFunction(()=>document.querySelector('.cm-task-heading')?.textContent.includes('已取消'))
 assert.ok(writeHeaders.every(h=>!h['x-cardmig-token']&&h['x-cardmig-csrf']?.length===43))
 console.log(JSON.stringify({status:'completed',page_errors:errors,submitted:true,title:await page.title()}))
}finally{await browser.close()}
