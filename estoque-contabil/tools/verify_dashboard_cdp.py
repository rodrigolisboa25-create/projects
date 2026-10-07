"""Smoke-check the local dashboard through an existing Chrome CDP endpoint."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect


def page_target() -> dict[str, str]:
    port = int(os.getenv("OPS_CDP_PORT", "9223"))
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
        targets = json.load(response)
    return next(item for item in targets if item.get("type") == "page" and item.get("url", "").startswith("http://127.0.0.1:8765"))


def main() -> None:
    target = page_target()
    port = int(os.getenv("OPS_CDP_PORT", "9223"))
    next_id = 0
    with connect(target["webSocketDebuggerUrl"], origin=f"http://127.0.0.1:{port}") as ws:
        def command(method: str, params: dict | None = None) -> dict:
            nonlocal next_id
            next_id += 1
            current = next_id
            ws.send(json.dumps({"id": current, "method": method, "params": params or {}}))
            while True:
                message = json.loads(ws.recv())
                if message.get("id") == current:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})

        def evaluate(expression: str, await_promise: bool = False):
            result = command(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": await_promise,
                },
            )
            return result.get("result", {}).get("value")

        command("Runtime.enable")
        command("Page.enable")
        command(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1680, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
        )
        command("Page.reload", {"ignoreCache": True})
        time.sleep(1)
        evaluate(
            """
            (async()=>{
              if (!document.body.classList.contains('authenticated')) {
                document.getElementById('login-email').value='rodrigo.lisboa@gruposbf.com.br';
                document.getElementById('login-form').requestSubmit();
              }
              return true;
            })()
            """,
            await_promise=True,
        )
        deadline = time.time() + 90
        while time.time() < deadline:
            ready = evaluate(
                "document.body.classList.contains('authenticated') && document.getElementById('system-loader').classList.contains('hidden')"
            )
            if ready:
                break
            time.sleep(1)
        else:
            raise TimeoutError("Dashboard did not finish authentication/loading")

        result = evaluate(
            """
            (()=>{
              activate('overview', false, false);
              const options=[...document.querySelectorAll('#global-period option')].map(x=>x.textContent.trim());
              const lifecycle=document.getElementById('chart-lifecycle-aging');
              const trend=document.getElementById('chart-trend');
              const pareto=document.getElementById('chart-pmm-pareto');
              const pie=document.getElementById('chart-cost-composition');
              return {
                periodOptions: options,
                selectorHasRowCounts: options.some(x=>/linhas?/i.test(x)),
                lifecycleBars: lifecycle.querySelectorAll('.lifecycle-bar').length,
                lifecycleActiveBars: lifecycle.querySelectorAll('.lifecycle-bar.active').length,
                lifecycleInactiveBars: lifecycle.querySelectorAll('.lifecycle-bar.inactive').length,
                lifecycleCategories: [...lifecycle.querySelectorAll('.lifecycle-category')].map(x=>x.textContent.trim()),
                lifecycleAxisLabels: [...lifecycle.querySelectorAll('.lifecycle-axis-label')].map(x=>x.textContent.trim()),
                lifecycleValueLabels: [...lifecycle.querySelectorAll('.lifecycle-value')].map(x=>x.textContent.trim()),
                lifecycleLabelOverlaps: (()=>{const labels=[...lifecycle.querySelectorAll('.lifecycle-value')],hits=[];for(let i=0;i<labels.length;i++){const a=labels[i].getBoundingClientRect();for(let j=i+1;j<labels.length;j++){const b=labels[j].getBoundingClientRect();if(a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top)hits.push([labels[i].textContent,labels[j].textContent])}}return hits})(),
                trendAxisLabels: [...trend.querySelectorAll('.trend-axis-label')].map(x=>x.textContent.trim()),
                trendPointLabels: [...trend.querySelectorAll('.trend-point-value')].map(x=>x.textContent.trim()),
                trendBars: trend.querySelectorAll('.trend-bar').length,
                trendHasQuantityLine: !!trend.querySelector('.trend-qty'),
                trendLabelOverlaps: (()=>{const labels=[...trend.querySelectorAll('.trend-point-value')],hits=[];for(let i=0;i<labels.length;i++){const a=labels[i].getBoundingClientRect();for(let j=i+1;j<labels.length;j++){const b=labels[j].getBoundingClientRect();if(a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top)hits.push([labels[i].textContent,labels[j].textContent])}}return hits})(),
                pmmParetoBars: pareto.querySelectorAll('.pmm-bar').length,
                pmmParetoLine: !!pareto.querySelector('.pareto-line'),
                pmmValues: [...pareto.querySelectorAll('.pareto-value')].map(x=>x.textContent.trim()),
                costPieSlices: pie.querySelectorAll('.pie-slice').length,
                costPieLegend: [...pie.querySelectorAll('.pie-label')].map(x=>x.textContent.trim()),
                currentPeriod: document.getElementById('global-period').value,
                consoleErrors: window.__opsVerificationErrors || []
              };
            })()
            """
        )
        evaluate("activate('all-brazil', false, true)")
        deadline = time.time() + 30
        while time.time() < deadline:
            icon_ready = evaluate("!!document.querySelector('.drive-year .collapse-icon svg')")
            if icon_ready:
                break
            time.sleep(0.5)
        result["allBrazilIcon"] = evaluate(
            """
            (()=>{const x=document.querySelector('.drive-year .collapse-icon');if(!x)return null;const r=x.getBoundingClientRect();return {svg:!!x.querySelector('svg'),width:r.width,height:r.height,borderRadius:getComputedStyle(x).borderRadius}})()
            """
        )
        result["pmmFilterCounts"] = evaluate(
            """
            (()=>{const select=document.getElementById('pmm-dimension'),out={};for(const value of ['period','division','plant','location','season']){select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));out[value]=document.querySelectorAll('#chart-pmm-pareto .pmm-bar').length}select.value='period';select.dispatchEvent(new Event('change',{bubbles:true}));return out})()
            """
        )
        result["reportCapabilities"] = evaluate(
            """
            (async()=>{
              const period=document.getElementById('global-period').value;
              const context=await fetch('/api/agent/context?period='+encodeURIComponent(period),{credentials:'same-origin'}).then(r=>r.json());
              const response=await fetch('/api/reports/email',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrfToken},body:JSON.stringify({period:document.getElementById('global-period').value,recipient:'nobody@example.com'})});
              const presentationResponse=await fetch('/api/reports/presentation/context?period='+encodeURIComponent(period),{credentials:'same-origin'});
              const presentation=await presentationResponse.json();
              return {tools:Object.keys(context.local_tools||{}),removedEndpointStatus:response.status,presentationStatus:presentationResponse.status,slideOutline:(presentation.slide_outline||[]).length};
            })()
            """,
            await_promise=True,
        )
        result["optimusPlainUrl"] = evaluate(
            """
            (()=>{
              const frame=document.querySelector('#agent-container iframe');
              const win=frame?.contentWindow,doc=frame?.contentDocument;
              if(!win||!doc||typeof win.addMessage!=='function')return {ready:false};
              win.addMessage('assistant','Acesse a apresentação:\nhttps://docs.google.com/presentation/d/teste/edit');
              win.addMessage('assistant','PDF preparado.\n/api/reports/pdf/download?period=2026-08');
              const links=[...doc.querySelectorAll('.message.assistant .bubble a')];
              const slide=links.at(-2),pdf=links.at(-1);
              return {
                ready:true,
                slide:{href:slide?.href||'',target:slide?.target||'',rel:slide?.rel||'',text:slide?.textContent||''},
                pdf:{href:pdf?.href||'',download:pdf?.hasAttribute('download')||false,className:pdf?.className||'',text:pdf?.textContent||''}
              };
            })()
            """
        )
        result["installerStatus"] = evaluate(
            """
            (async()=>{
              activate('settings',false,false);
              await loadSettings(true);
              const env=await fetch('/api/settings/environment',{credentials:'same-origin'}).then(r=>r.json());
              const download=await fetch('/api/installer/download',{credentials:'same-origin',headers:{Range:'bytes=0-0'}});
              if(download.body)download.body.cancel();
              return {
                available:env.installer_available,
                version:env.installer_version,
                source:env.installer_source,
                sha256Length:String(env.installer_sha256||'').length,
                metaText:document.getElementById('installer-meta')?.textContent||'',
                downloadStatus:download.status,
                downloadVersion:download.headers.get('x-ops-installer-version'),
                contentDisposition:download.headers.get('content-disposition')
              };
            })()
            """,
            await_promise=True,
        )
        result["governanceStatus"] = evaluate(
            """
            (async()=>{
              activate('governance',false,false);
              await loadGovernance();
              return {
                controls:document.querySelectorAll('#governance-controls .control').length,
                structures:document.querySelectorAll('#governance-structures .control').length,
                sourceText:document.getElementById('governance-source')?.textContent||'',
                hasFalseBlockingClaim:/conflitos relevantes bloqueiam/i.test(document.querySelector('[data-panel="governance"]')?.textContent||'')
              };
            })()
            """,
            await_promise=True,
        )
        result["healthCenter"] = evaluate(
            """
            (async()=>{
              activate('health',false,false);
              await loadHealthCenter();
              return {
                cards:document.querySelectorAll('#health-grid .health-card').length,
                score:document.getElementById('health-score')?.textContent||'',
                titles:[...document.querySelectorAll('#health-grid .health-card h2')].map(x=>x.textContent.trim()),
                lights:[...document.querySelectorAll('#health-grid .health-light')].map(x=>{const style=getComputedStyle(x),box=x.getBoundingClientRect();return {width:Math.round(box.width),height:Math.round(box.height),cssWidth:style.width,cssHeight:style.height,inlineSize:style.inlineSize,blockSize:style.blockSize,minWidth:style.minWidth,maxWidth:style.maxWidth,display:style.display,boxSizing:style.boxSizing,background:style.backgroundColor}}),
                animatedAlerts:[...document.querySelectorAll('#health-grid .health-card.warning,#health-grid .health-card.critical')].map(x=>({title:x.querySelector('h2')?.textContent.trim(),animation:getComputedStyle(x,'::before').animationName})),
                lightRules:[...document.styleSheets].flatMap(sheet=>[...sheet.cssRules]).filter(rule=>rule.cssText?.includes('health-light')).map(rule=>rule.cssText),
                supportPresent:document.getElementById('health-dialog-support')?.textContent==='transformacao_digital@gruposbf.com.br'
              };
            })()
            """,
            await_promise=True,
        )
        health_shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        health_output = Path.home() / "AppData/Local/Temp/ops_health_center_verified.png"
        health_output.write_bytes(base64.b64decode(health_shot["data"]))
        result["healthScreenshot"] = str(health_output)
        result["standaloneHtml"] = evaluate(
            """
            (async()=>{
              const response=await fetch('/api/reports/html/download?period='+encodeURIComponent(state.period),{credentials:'same-origin'});
              const text=await response.text();
              return {status:response.status,size:text.length,doctype:text.startsWith('<!doctype html>'),title:(text.match(new RegExp('<title>(.*?)</title>','i'))||[])[1]||'',hasOldBrand:text.includes('Ops Contábil'),contentDisposition:response.headers.get('content-disposition')||'',hasShareDialog:!!document.getElementById('html-share-dialog'),hasLocalhost:text.includes('127.0.0.1'),hasN8n:/n8n/i.test(text),hasAppsScript:text.includes('script.google')};
            })()
            """,
            await_promise=True,
        )
        result["htmlShareDialog"] = evaluate(
            """
            (async()=>{
              document.getElementById('share-html').click();
              for(let i=0;i<80&&!document.getElementById('html-share-dialog').open;i++)await new Promise(resolve=>setTimeout(resolve,100));
              const dialog=document.getElementById('html-share-dialog');
              const result={open:dialog.open,filename:document.getElementById('html-share-filename')?.textContent||'',explainsLocalPath:(dialog.textContent||'').toLowerCase().includes('file:///'),downloadButton:!!document.getElementById('html-share-download')};
              if(dialog.open)dialog.close();
              return result;
            })()
            """,
            await_promise=True,
        )
        result["pdfDownload"] = evaluate(
            """
            (async()=>{
              async function attempt(){
                const started=performance.now(),response=await fetch('/api/reports/pdf/download?period='+encodeURIComponent(state.period),{credentials:'same-origin'}),buffer=await response.arrayBuffer(),bytes=new Uint8Array(buffer.slice(0,5));
                return {status:response.status,durationMs:Math.round(performance.now()-started),contentType:response.headers.get('content-type')||'',contentDisposition:response.headers.get('content-disposition')||'',size:buffer.byteLength,magic:String.fromCharCode(...bytes)};
              }
              return {first:await attempt(),cached:await attempt()};
            })()
            """,
            await_promise=True,
        )
        result["accessManagement"] = evaluate(
            """
            (async()=>{
              activate('settings',false,false);
              await loadSettings(true);
              return {
                shareButton:document.getElementById('share-html')?.textContent.trim()||'',
                deleteButtons:[...document.querySelectorAll('#access-list .access-user-actions button')].filter(button=>button.textContent.trim()==='Excluir').map(button=>({disabled:button.disabled,email:button.closest('.access-user')?.querySelector('b')?.textContent||''})),
                deleteDialog:!!document.getElementById('access-delete-dialog')
              };
            })()
            """,
            await_promise=True,
        )
        evaluate("activate('overview', false, false)")
        shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        output = Path.home() / "AppData/Local/Temp/ops_dashboard_verified.png"
        output.write_bytes(base64.b64decode(shot["data"]))
        result["screenshot"] = str(output)
        evaluate("document.getElementById('chart-trend').scrollIntoView({block:'center'})")
        time.sleep(0.5)
        trend_shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        trend_output = Path.home() / "AppData/Local/Temp/ops_trend_verified.png"
        trend_output.write_bytes(base64.b64decode(trend_shot["data"]))
        result["trendScreenshot"] = str(trend_output)
        evaluate("document.getElementById('chart-pmm-pareto').scrollIntoView({block:'center'})")
        time.sleep(0.5)
        artifact_shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        artifact_output = Path.home() / "AppData/Local/Temp/ops_new_charts_verified.png"
        artifact_output.write_bytes(base64.b64decode(artifact_shot["data"]))
        result["newChartsScreenshot"] = str(artifact_output)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
