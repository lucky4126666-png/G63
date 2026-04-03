import {useEffect,useState} from "react";
import axios from "axios";

function App(){
 const [users,setUsers]=useState([])

 useEffect(()=>{
  axios.get("/api/users").then(r=>setUsers(r.data))
 },[])

 return(
  <div>
   <h1>G63 SaaS Panel</h1>

   {users.map(u=>(
    <div key={u[0]}>
      User: {u[0]}
    </div>
   ))}
  </div>
 )
}

export default App;
