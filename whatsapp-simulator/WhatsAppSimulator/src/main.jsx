import React from 'react';
import {createRoot} from 'react-dom/client';
import KiranaAI from './KiranaAI';
import Messenger from './Messenger';
import './standalone.css';
const {mode,shop_url}=await fetch('/config').then(r=>r.json());
const shop=location.search==='?shop';
async function api(path,method='GET',body){
 const form=body instanceof FormData;
 const r=await fetch('/api/'+path,{method,headers:body&&!form?{'Content-Type':'application/json'}:{},body:body?(form?body:JSON.stringify(body)):undefined});
 const d=await r.json();if(!r.ok)throw Error(d.detail||'Could not complete the request');return d
}
createRoot(document.getElementById('root')).render(<><div className="bar"><b>WhatsApp Simulator</b><span>{mode==='standalone'?'Local demo':'Connected mode'}</span><a href={shop?'/' : '/?shop'} target="_blank" rel="noreferrer">{shop?'Customer chat':'Shop inbox'} ↗</a></div><Messenger api={api} shop={shop} assistant={<KiranaAI api={api} connected={mode==='connected'} shop={shop} ownerUrl={shop_url}/>}/></>);
