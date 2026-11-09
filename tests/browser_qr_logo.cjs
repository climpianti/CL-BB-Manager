// Local fixtures only; checks actual panel preview and browser-rendered SVG decoding.
const fs=require('node:fs');const path=require('node:path');const {spawnSync}=require('node:child_process');
const {chromium}=require(process.env.CL_BB_PLAYWRIGHT_MODULE||'playwright-core');
const python=process.env.CL_BB_PYTHON||'python';
const root=path.resolve(__dirname,'../custom_components/cl_bb_manager');
const generated=spawnSync(python,[path.join(__dirname,'qr_logo_fixture.py')],{encoding:'utf8',maxBuffer:2000000});
if(generated.status!==0)throw Error(generated.stderr);
const fixture=JSON.parse(generated.stdout);
function decode(base64){
 const script="import sys,json,base64;from io import BytesIO;from PIL import Image;import zxingcpp;i=Image.open(BytesIO(base64.b64decode(sys.stdin.read()))).convert('RGB');d=zxingcpp.read_barcode(i);colors=i.getcolors(i.width*i.height);print(json.dumps({'decoded':bool(d and d.text==sys.argv[1]),'logoVisible':any(b>80 and g>30 and r<50 for n,(r,g,b) in colors)}))";
 const result=spawnSync(python,['-c',script,fixture.url],{input:base64,encoding:'utf8'});if(result.status!==0)throw Error(result.stderr);const d=JSON.parse(result.stdout);if(!d.decoded||!d.logoVisible)throw Error('Logo or QR decoding failed');return d;
}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CL_BB_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote'],headless:true});const results=[];
 try{
  for(const role of ['admin','operator'])for(const width of [390,1366]){
   const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const snapshot={role,structure:'Residenza Aurora',gates:[{id:'test-door',name:'Ingresso',kind:'shared',enabled:true,physical_enabled:true,physical_qr_prepared:true}],bookings:[],events:[],access_history:[],hardware_control:'enabled',qr_branding:role==='admin'?fixture.status:undefined};
   await page.route('**/*',async route=>{const url=new URL(route.request().url());if(url.origin!=='https://qr-test.invalid')throw Error('External request blocked');
    if(url.pathname==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#061324"><cl-bb-manager-panel></cl-bb-manager-panel><script src="/panel.js"></script><script>document.querySelector('cl-bb-manager-panel').hass={user:{id:'${role}'},connection:{},callWS:async q=>{if(q.type==='cl_bb_manager/list')return ${JSON.stringify(snapshot)};if(q.type==='cl_bb_manager/physical_qr')return ${JSON.stringify({...fixture.artwork,gate_id:'test-door'})};throw Error('Unexpected operation');}};</script></body></html>`});
    if(url.pathname==='/panel.js')return route.fulfill({contentType:'text/javascript; charset=utf-8',body:fs.readFileSync(path.join(root,'frontend/panel.js'))});
    if(url.pathname.startsWith('/cl_bb_manager_static/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':'image/svg+xml',body:fs.readFileSync(path.join(root,'frontend',path.basename(url.pathname)))});
    return route.fulfill({status:404,body:'Not found'});
   });
   await page.goto('https://qr-test.invalid/');await page.getByRole('navigation').getByRole('button',{name:'QR delle porte',exact:true}).click();await page.getByRole('button',{name:'Mostra / scarica QR',exact:true}).click();
   const qr=page.locator('cl-bb-manager-panel').locator('.qr-print img');await qr.waitFor();await qr.evaluate(img=>img.decode());
   if(await page.getByRole('link',{name:/Scarica QR/}).count()!==2)throw Error('Missing export');
   const raster=await page.evaluate(async svg=>{const img=new Image();img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);await img.decode();const canvas=document.createElement('canvas');canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;canvas.getContext('2d').drawImage(img,0,0);return canvas.toDataURL('image/png').split(',')[1];},fixture.artwork.svg);
   decode(raster);decode(fixture.artwork.png_base64);decode((await qr.screenshot()).toString('base64'));
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Overflow');
   if(errors.length)throw Error(errors.join('\n'));
   if(process.env.CL_BB_SCREENSHOT_DIR){fs.mkdirSync(process.env.CL_BB_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.CL_BB_SCREENSHOT_DIR,`qr-logo-${role}-${width}.png`),fullPage:true});}
   results.push({role,width,svgDecoded:true,pngDecoded:true,previewDecoded:true,embeddedLogoVisible:true,pageErrors:0});await context.close();
  }
  console.log(JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
