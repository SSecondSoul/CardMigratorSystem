// Only local disposable Flask test server; never connects to a user's API or model.
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'
const config=JSON.parse(fs.readFileSync(0,'utf8'))
const browser=await puppeteer.launch({executablePath:config.executable,headless:true})
try{
 const page=await browser.newPage(),errors=[]
 page.on('pageerror',e=>errors.push(e.message))
 await page.goto(config.url,{waitUntil:'networkidle0'})
 await page.waitForSelector('.migration-form')
 await page.locator('.migration-form textarea').fill(config.source)
 await page.locator('.migration-form input[type=password]').fill(config.token)
 const checkboxes=await page.$$('.migration-form input[type=checkbox]')
 for(const box of checkboxes)await box.click()
 await page.click('.migration-form .primary-button')
 await page.waitForFunction(()=>document.querySelector('.migration-main')?.textContent.includes('排队'),{timeout:10000})
 console.log(JSON.stringify({status:'completed',page_errors:errors,submitted:true,title:await page.title()}))
}finally{await browser.close()}
