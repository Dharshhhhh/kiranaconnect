import React,{useRef,useState} from 'react';
import {Send} from 'lucide-react';

export default function KiranaAI({api,connected,shop,ownerUrl}){
 const [log,update]=useState([]),[draft,write]=useState(''),[busy,wait]=useState(false),[pending,propose]=useState(null);
 const lock=useRef(false);
 const prompts=connected&&shop?['Today’s sales','Low-stock products','Summary of today’s activity']:['How do I order?','Show recent messages',...(connected?['Show catalog','Order 5 kg Rice','My order status']:[])];
 async function ask(question,confirmation){
  if(!question.trim()||lock.current)return;
  lock.current=true;wait(true);write('');update(l=>[...l,{text:question,out:true}]);
  try{
   let answer;
   if(connected&&shop){
    const result=await api(confirmation?'chat/confirm':'chat','POST',confirmation||{message:question});
    propose(result.confirm?{tool:result.tool,args:result.args,request_id:crypto.randomUUID()}:null);
    answer=result.answer+(result.confirm?' '+JSON.stringify(result.args):'');
   }else{
    const q=question.toLowerCase();
    if(connected && confirmation){
     await api('customer/message','POST',confirmation);
     propose(null);
     answer='Your order request was sent to the shop. Ask “My order status” to check reservations.';
    }else if(connected && /order status|my orders|track/.test(q)){
     const {messages}=await api('customer/thread');
     const orders=messages.filter(m=>m.ref);
     answer=orders.map(m=>m.ref+' · '+m.order_status+' · ₹'+(m.amount/100).toFixed(2)).join('\n')||'No recorded orders yet. Check the shop conversation for processing or review messages.';
    }else if(connected && /^(?:please )?(?:order|buy|reserve)\s+.+/i.test(question.trim())){
     const body=question.trim().replace(/^(?:please )?(?:order|buy|reserve)\s+/i,'Order ');
     propose({body,nonce:crypto.randomUUID()});
     answer='Send this request to the shop? '+body;
    }else if(/recent|history|summary/.test(q)){
     if(shop){const rows=await api('inbox');answer=rows.map(r=>r.name+': '+r.body).join('\n')||'No conversations yet.'}
     else{const data=await api('customer/thread');answer=data.messages.slice(-5).map(m=>(m.side==='shop'?'Shop':'You')+': '+m.body).join('\n')||'No messages yet.'}
    }else if(/catalog|price|products/.test(q)&&connected){
     const data=await api('customer/thread');const matches=data.catalog.filter(p=>q.includes(p.name.toLowerCase()));answer=(matches.length?matches:data.catalog).map(p=>p.name+' · ₹'+(p.sell/100)+'/'+p.unit).join('\n')||'No catalog items yet.';
    }else if(/order|buy|rice/.test(q)){answer='Open KiranaConnect Business in Chats and send “Rice 5 kg”. '+(connected?'Your shop will check availability and reserve the items.':'In local demo mode this sends a message. Connected mode adds stock reservation.')}
    else if(/photo|image|screenshot/.test(q)){answer='Open the shop conversation, select the paperclip, choose your image and press Send.'}
    else answer='I can explain ordering, help with screenshots or show recent messages.'+(connected?' Ask “Show catalog” for current shop prices.':' Connect KiranaConnect to use its store assistant.');
   }
   update(l=>[...l,{text:answer}])
  }catch(e){update(l=>[...l,{text:e.message}])}finally{lock.current=false;wait(false)}
 }
 return <><div className="waScroll"><p className="waBubble">{connected&&shop?'Ask Kirana AI about the store.':connected?'Ask about the catalog, ordering or your conversation.':'Local demo assistant · Ask about orders or messages.'}</p>{connected&&shop&&<a href={ownerUrl} target="_blank" rel="noreferrer">Sign in to KiranaConnect as owner ↗</a>}{prompts.map(q=><button key={q} className="aiPrompt" disabled={busy} onClick={()=>ask(q)}>{q}</button>)}{log.map((r,i)=><div ref={el=>{if(el&&i===log.length-1)el.scrollIntoView({block:'nearest'})}} key={i} className={'waBubble '+(r.out?'out':'in')}>{r.text}</div>)}{pending&&<button disabled={busy} onClick={()=>ask('Confirm',pending)}>Confirm action</button>}</div><form className="waCompose" onSubmit={e=>{e.preventDefault();ask(draft)}}><input placeholder="Message Kirana AI" value={draft} onChange={e=>write(e.target.value)} maxLength={1000}/><button className="waSend" disabled={busy||!draft.trim()} aria-label="Send to Kirana AI"><Send/></button></form></>
}
