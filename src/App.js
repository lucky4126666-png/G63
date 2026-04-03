import {useEffect,useState} from "react";
import axios from "axios";

function App(){

 const [users,setUsers]=useState([])
 const [groups,setGroups]=useState([])

 useEffect(()=>{
  load()
  setInterval(load,3000)
 },[])

 function load(){
  axios.get("/api/users").then(r=>setUsers(r.data))
  axios.get("/api/groups").then(r=>setGroups(r.data))
 }

 function ban(uid,gid){
  axios.post("/api/ban",{uid,gid})
 }

 function lock(gid){
  axios.post("/api/lock",{gid})
 }

 return(
  <div style={{padding:20, background:"#0f172a", color:"white"}}>

   <h1>🚀 G63 SaaS Panel</h1>

   <h2>👥 Users</h2>
   {users.map(u=>(
    <div key={u[0]} style={{borderBottom:"1px solid #333", padding:10}}>
      {u[0]} | role: {u[2]}
      <button onClick={()=>ban(u[0], groups[0]?.[0])}>
        Ban
      </button>
    </div>
   ))}

   <h2>👥 Groups</h2>
   {groups.map(g=>(
    <div key={g[0]}>
      {g[0]} | {g[1] ? "🔒" : "🔓"}
      <button onClick={()=>lock(g[0])}>Toggle</button>
    </div>
   ))}

  </div>
 )
}

export default App;
