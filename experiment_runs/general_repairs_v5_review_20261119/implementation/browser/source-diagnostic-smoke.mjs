// Test-only: a built workbench and disposable local Flask database. No model.
import fs from 'node:fs'
import puppeteer from 'puppeteer-core'
const config=JSON.parse(fs.readFileSync(0,'utf8'))
const browser=await puppeteer.launch({executablePath:config.executable,headless:true})
try{
  const page=await browser.newPage(),errors=[],origin=new URL(config.url).origin
  page.on('pageerror',e=>errors.push(e.message))
  await page.setRequestInterception(true)
  page.on('request',request=>new URL(request.url()).origin===origin?request.continue():request.abort())
  await page.goto(config.url,{waitUntil:'networkidle0'})
  await page.waitForSelector('.migration-main .text-button')
  await page.click('.migration-main .text-button')
  await page.waitForSelector('.source-diagnostics',{timeout:10000})
  const text=await page.$eval('.source-diagnostics',el=>el.textContent)
  const excerpt=await page.$eval('.source-diagnostics pre',el=>el.textContent)
  console.log(JSON.stringify({status:'completed',page_errors:errors,
    code_visible:text.includes(config.error_code),location_visible:/第\s*\d+\s*行，第\s*\d+\s*列/.test(text),
    zero_model_visible:text.includes('尚未调用模型'),excerpt_as_text:excerpt.includes('<span>')&&!(await page.$('.source-diagnostics pre span'))}))
}finally{await browser.close()}
