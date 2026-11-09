// Optional real-browser locale test. All page requests go to loopback-only fakes.
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const path=require('node:path');
const readline=require('node:readline');
const fs=require('node:fs');
const {chromium}=require(process.env.CL_BB_PLAYWRIGHT_MODULE||'playwright-core');
(async()=>{
 const server=spawn(process.env.CL_BB_PYTHON||'python',[path.join(__dirname,'guest_language_server.py')],{stdio:['ignore','pipe','pipe']});
 let errors='';server.stderr.on('data',chunk=>errors+=chunk);
 let browser;
 try{
  const lines=readline.createInterface({input:server.stdout});
  const port=await Promise.race([once(lines,'line').then(([line])=>line),once(server,'exit').then(()=>{throw Error('Fixture exited: '+errors);}),new Promise((_,reject)=>setTimeout(()=>reject(Error('Fixture startup timed out')),10000).unref())]);
  if(!/^\d+$/.test(port))throw Error('Invalid loopback port');
  browser=await chromium.launch({executablePath:process.env.CL_BB_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote'],headless:true});
  const results=[];let expectedCommands=0;
  for(const locale of ['it-IT','en-US'])for(const door of ['strada','scala']){
   const language=locale.startsWith('en')?'en':'it';
   const context=await browser.newContext({locale,viewport:{width:390,height:844}});
   const page=await context.newPage();const pageErrors=[];let browserLanguageHeader;
   page.on('pageerror',error=>pageErrors.push(error.message));
   await page.route('**/*',async route=>{
    const req=route.request();const url=new URL(req.url());
    if(url.origin!=='https://hotel.example.org')throw Error('Unexpected external request blocked');
    const headers=await req.allHeaders();
    if(url.pathname.includes('/physical/')&&req.method()==='GET')browserLanguageHeader=headers['accept-language'];
    const response=await route.fetch({url:`http://127.0.0.1:${port}${url.pathname}${url.search}`,headers:{...headers,host:'hotel.example.org'}});
    await route.fulfill({response});
   });
   const token=(door+'-'+language+'-browser-fixture').padEnd(48,'x');
   const response=await page.goto('https://hotel.example.org/api/cl_bb_manager/physical/'+token);
   if(response.status()!==200||response.headers()['content-language']!==language)throw Error('Language response mismatch');
   if(await page.locator('html').getAttribute('lang')!==language)throw Error('HTML language mismatch');
   await page.getByLabel(language==='en'?'Access code':'Codice di accesso').fill('00000000');
   const failed=page.waitForResponse(r=>r.request().method()==='POST');await page.getByRole('button',{name:language==='en'?'Continue':'Continua',exact:true}).click();
   if((await failed).status()!==403)throw Error('Wrong code was not rejected');
   await page.getByRole('link',{name:language==='en'?'Reopen the code page':'Riapri la pagina del codice',exact:true}).click();
   await page.getByLabel(language==='en'?'Access code':'Codice di accesso').fill('12345678');
   const accepted=page.waitForResponse(r=>r.request().method()==='POST');await page.getByRole('button',{name:language==='en'?'Continue':'Continua',exact:true}).click();
   if((await accepted).status()!==200)throw Error('Controlled code was not accepted');
   await page.getByText(language==='en'?'Request sent':'Richiesta inviata',{exact:true}).waitFor();
   const status=await (await context.request.get(`http://127.0.0.1:${port}/__test_status`)).json();
   expectedCommands++;if(status.commands!==expectedCommands)throw Error('Unexpected simulated command count');
   if(pageErrors.length)throw Error(pageErrors.join('\n'));
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Horizontal overflow');
   if(process.env.CL_BB_SCREENSHOT_DIR){fs.mkdirSync(process.env.CL_BB_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.CL_BB_SCREENSHOT_DIR,`guest-${door}-${language}.png`),fullPage:true});}
   results.push({language,door,browserLanguageHeader,wrongCode:403,accepted:200,fakeCommands:1});await context.close();
  }
  console.log(JSON.stringify(results,null,2));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(error=>{console.error(error);process.exitCode=1;});
