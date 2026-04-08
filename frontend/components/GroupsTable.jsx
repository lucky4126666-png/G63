function GroupsTable(){
  const [data,setData] = React.useState([])

  React.useEffect(()=>{
    fetch("/admin/groups")
      .then(r=>r.json())
      .then(d=>setData(d.data))
  },[])

  return (
    <div>
      <h2>👥 Groups</h2>
      <table border="1">
        <tr><th>Name</th><th>ID</th></tr>
        {data.map(g=>(
          <tr>
            <td>{g[1]}</td>
            <td>{g[0]}</td>
          </tr>
        ))}
      </table>
    </div>
  )
}
