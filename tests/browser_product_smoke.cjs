// Optional isolated Chromium smoke: all network requests are intercepted.
const fs=require('node:fs');const path=require('node:path');
const {chromium:playwright}=require(process.env.CL_BB_PLAYWRIGHT_MODULE || 'playwright-core');
const root=path.resolve(__dirname,'../custom_components/cl_bb_manager');
(async()=>{
 const browser=await playwright.launch({executablePath:process.env.CL_BB_CHROMIUM_PATH,args:["--no-sandbox","--disable-dev-shm-usage","--no-zygote","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],headless:true});
 const results=[];
 for(const role of ['admin','operator'])for(const width of [390,1366]){
  const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const data={role,structure:'Residenza Aurora',gates:[{id:'g1',name:'Ingresso principale',enabled:true,kind:'shared',physical_enabled:true,physical_qr_prepared:true,entity_id:'switch.entrance',action:'switch.turn_on',pulse_seconds:2}],bookings:[],events:[],access_history:[],hardware_control:'enabled',public_origin:'https://hotel.example.org',public_access_enabled:true};
  await page.route('https://cl-bb-test.invalid/**',async route=>{
   const file=new URL(route.request().url()).pathname;
   if(file==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#061324"><cl-bb-manager-panel></cl-bb-manager-panel><script src="/panel.js"></script><script>document.querySelector('cl-bb-manager-panel').hass={user:{id:'qa-${role}'},connection:{},callWS:async request=>{if(request.type==='cl_bb_manager/list')return ${JSON.stringify(data)};if(request.type==='cl_bb_manager/shelly_relays')return {relays:[{entity_id:'switch.new_gate',name:'Nuovo ingresso',model:'Shelly 1 Mini Gen3'}]};throw Error('Unexpected QA request: '+request.type);}};</script></body></html>`});
   if(file==='/panel.js')return route.fulfill({contentType:'text/javascript; charset=utf-8',body:fs.readFileSync(path.join(root,'frontend/panel.js'),'utf8')});
   if(file.startsWith('/cl_bb_manager_static/')){const name=path.basename(file);return route.fulfill({contentType:name.endsWith('.css')?'text/css':'image/svg+xml',body:fs.readFileSync(path.join(root,'frontend',name))});}
   return route.fulfill({status:404,body:'Not found'});
  });
  await page.goto('https://cl-bb-test.invalid/');await page.getByRole('button',{name:'Prenotazioni',exact:true}).waitFor();
  if(role==='operator' && await page.getByRole('button',{name:'Varchi',exact:true}).count())throw Error('Admin navigation exposed');
  const tabs=role==='admin'?['Panoramica','Prenotazioni','QR delle porte','Registro accessi','Varchi','Impostazioni']:['Panoramica','Prenotazioni','QR delle porte','Registro accessi'];
  for(const tab of tabs){await page.getByRole('button',{name:tab,exact:true}).click();if(tab==='Varchi'){await page.getByRole('button',{name:'Cerca dispositivi',exact:true}).click();await page.getByRole('button',{name:'Configura e prepara QR',exact:true}).waitFor();}
   const visible=await page.locator('cl-bb-manager-panel').locator('main').innerText();if(/demo|pilota|qr temporane|soli varchi virtuali/i.test(visible))throw Error('Retired mode label on '+tab);
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);if(overflow)throw Error('Horizontal overflow '+role+' '+width+' '+tab);
  }
  await page.getByRole('button',{name:role==='admin'?'Varchi':'Prenotazioni',exact:true}).click();
  if(process.env.CL_BB_SCREENSHOT_DIR){fs.mkdirSync(process.env.CL_BB_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.CL_BB_SCREENSHOT_DIR,`panel-${role}-${width}.png`),fullPage:true});}
  if(errors.length)throw Error(errors.join('\n'));
  results.push({role,width,tabs:tabs.length,pageErrors:errors.length,horizontalOverflow:false});await context.close();
 }
 await browser.close();console.log(JSON.stringify(results,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
