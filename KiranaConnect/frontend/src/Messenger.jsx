import React,{useEffect,useRef,useState} from 'react';
import {MessageCircle,Search,Paperclip,Send,ShoppingBasket,Smile,Store,ArrowLeft,Check,CheckCheck,X,Image as ImageIcon} from 'lucide-react';
import './messenger.css';

export default function Messenger({api,shop=false,assistant}){
 const [ready,readySet]=useState(shop),[name,nameSet]=useState(''),[threads,list]=useState([]),[cid,select]=useState(null),[messages,show]=useState([]),[catalog,stock]=useState([]),[search,filter]=useState(''),[draft,write]=useState(''),[panel,panelSet]=useState(''),[err,fail]=useState(''),[sending,wait]=useState(false),[picked,pick]=useState(null);
 const [ai,setAi]=useState(false); const joining=useRef(false);
 const end=useRef(null),file=useRef(null),scroll=useRef(null),sendLock=useRef(false),version=useRef(0);
 const me=shop?'shop':'customer';
 async function reload(){
  const v=++version.current;
  if(shop){const all=await api('inbox');const msgs=cid?await api('inbox/'+cid):[];if(v!==version.current)return;list(all);show(msgs)}
  else{const data=await api('customer/thread');if(v!==version.current)return;nameSet(data.name);stock(data.catalog);show(data.messages);readySet(true)}
 }
 useEffect(()=>{let active=true;const load=()=>reload().catch(e=>{if(active&&e.message==='Start your chat'&&!joining.current){joining.current=true;api('customer/start','POST',{name:'Meena'}).then(reload).catch(e=>fail(e.message)).finally(()=>joining.current=false)}else if(active&&e.message!=='Start your chat')fail(e.message)});load();const id=setInterval(load,1800);return()=>{active=false;version.current++;clearInterval(id)}},[cid,ready]);
 useEffect(()=>{if(scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight},[messages.length,cid]);
 async function send(e){
  e?.preventDefault();if(sendLock.current||(!draft.trim()&&!picked))return;
  sendLock.current=true;wait(true);
  try{if(picked){const f=new FormData();f.append('file',picked);f.append('nonce',crypto.randomUUID());await api(shop?'inbox/'+cid+'/image':'customer/image','POST',f)}
   else await api(shop?'inbox/'+cid:'customer/message','POST',{body:draft.trim(),nonce:crypto.randomUUID()});
   pick(null);write('');panelSet('');fail('');await reload()
  }catch(e){fail(e.message)}finally{sendLock.current=false;wait(false)}
 }
 if(!ready)return <div className="waStart"><div><MessageCircle/><h2>Opening WhatsApp simulator…</h2>{err&&<p role="alert">{err}</p>}</div></div>;
 const contact=shop?threads.find(t=>t.id===cid)?.name:'KiranaConnect Business';
 const entries=shop?threads:[{id:1,name:'KiranaConnect Business',body:messages.at(-1)?.body||'Business account'}];
 const inThread=ai||!shop||Boolean(cid);
 return <div className={'wa '+(shop?'operator':'buyer')+' '+(inThread?'threadOpen':'')}>
 <div className="waRail"><MessageCircle size={26}/><span>{shop?'S':name[0]}</span></div>
 <div className="waList"><header><div><small>WhatsApp · Simulator</small><h2>Chats</h2></div><MessageCircle size={21}/></header><div className="waSearch"><Search size={17}/><input aria-label="Search chats" placeholder="Search chats" value={search} onChange={e=>filter(e.target.value)}/></div>
 {shop&&"kirana ai".includes(search.toLowerCase())&&<button className={"waRow "+(ai?"chosen":"")} onClick={()=>{select(null);setAi(true)}}><i>✦</i><div><b>Kirana AI</b><small>Ask about your store</small></div></button>}
 {entries.filter(t=>t.name.toLowerCase().includes(search.toLowerCase())).map(t=><button key={t.id} className={'waRow '+((shop?cid===t.id:true)?'chosen':'')} onClick={()=>{if(shop){setAi(false);select(t.id);show([]);write('');panelSet('')}}}><i>{t.name[0]}</i><div><b>{t.name}</b><small>{t.body}</small></div></button>)}
 {shop&&!threads.length&&<p className="waHint">Customer chats will appear here.</p>}{shop&&<a className="waLaunch" target="_blank" rel="noreferrer" href="/?customer">Open customer simulator ↗</a>}</div>
 <div className="waThread">{ai?<><header><button aria-label="Back to chats" onClick={()=>setAi(false)}><ArrowLeft/></button><i>✦</i><b>Kirana AI</b></header>{assistant}</>:inThread?<><header>{shop&&<button aria-label="Back to chats" onClick={()=>select(null)}><ArrowLeft size={19}/></button>}<i>{shop?contact?.[0]:<Store size={21}/>}</i><div><b>{contact}</b><small>{shop?'Customer':'Business account'}</small></div></header>
 <div className="waScroll" ref={scroll}>{messages.map((m,i)=>{const mine=m.side===me,day=m.at.slice(0,10);return <React.Fragment key={m.id}>{day!==messages[i-1]?.at.slice(0,10)&&<div className="waDate">{new Date(m.at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</div>}<div className={'waBubble '+(mine?'out':'in')}>{m.job&&<a target="_blank" rel="noreferrer" href={shop?'/api/jobs/'+m.job+'/image':'/api/customer/images/'+m.job}><img alt="Chat attachment" src={shop?'/api/jobs/'+m.job+'/image':'/api/customer/images/'+m.job}/></a>}{m.photo===1&&<img alt="Shop attachment" src={'/api/'+(shop?'shop':'customer')+'/photo/'+m.id}/>} {m.body}{m.ref&&<small>{m.ref} · ₹{(m.amount/100).toFixed(2)} · {m.order_status}</small>}{m.job&&<small>Screenshot · {m.job_status}</small>}<div className="waTime">{new Date(m.at).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'})}{mine&&(m.seen?<CheckCheck size={14} color="#279bcc" aria-label="Read"/>:<Check size={13} aria-label="Sent"/>)}</div></div></React.Fragment>})}<span ref={end}/></div>
 {panel==='catalog'&&<form className="waTools" onSubmit={e=>{e.preventDefault();const p=catalog[Number(e.target.product.value)];write('Order '+e.target.qty.value+' '+p.unit+' '+p.name);panelSet('')}}><label>Product<select name="product">{catalog.map((p,i)=><option key={p.name} value={i}>{p.name} · ₹{p.sell/100}/{p.unit}</option>)}</select></label><label>Quantity<input name="qty" type="number" step=".001" min=".001" defaultValue="1" required/></label><button disabled={!catalog.length}>Add to message</button></form>}
 {panel==='emoji'&&<div className="waTools">{['👍','🙏','😊','✅','🛒','❤️'].map(x=><button key={x} onClick={()=>{write(draft+x);panelSet('')}}>{x}</button>)}</div>}
 {picked&&<div className="waTools"><ImageIcon/>{picked.name}<button onClick={()=>pick(null)} aria-label="Remove attachment"><X/></button></div>}
 {err&&<p role="alert" className="waError">{err}</p>}
 <form className="waCompose" onSubmit={send}><button aria-label="Emoji" type="button" onClick={()=>panelSet(panel==='emoji'?'':'emoji')}><Smile/></button>{<><button aria-label="Attach screenshot" type="button" onClick={()=>file.current.click()}><Paperclip/></button><input ref={file} type="file" hidden accept="image/jpeg,image/png,image/webp" onChange={e=>{pick(e.target.files[0]);e.target.value=''}}/>{!shop&&<button aria-label="Order from catalog" title="Order from catalog" type="button" onClick={()=>panelSet(panel==='catalog'?'':'catalog')}><ShoppingBasket/></button>}</>}<input aria-label="Message" disabled={!!picked} placeholder="Type a message" value={draft} maxLength={1500} onChange={e=>write(e.target.value)}/><button disabled={sending||(!draft.trim()&&!picked)} className="waSend" aria-label="Send message"><Send size={20}/></button></form></>:<div className="waBlank"><MessageCircle size={42}/><h2>Shop inbox</h2><p>Select a conversation to reply.</p></div>}</div></div>
}
