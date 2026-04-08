function LogsTable(){
  const [data,setData] = React.useState([])

  React.useEffect(()=>{
    fetch("/admin/logs")
      .then(r=>r.json())
      .then(d=>setData(d.data))
  },[])

  return (
    <div>
      <h2>📊 Logs</h2>
      <table border="1">
        <tr><th>User</th><th>Action</th><th>Group</th><th>Time</th></tr>
        {data.map(l=>(
          <tr>
            <td>{l[0]}</td>
            <td>{l[1]}</td>
            <td>{l[2]}</td>
            <td>{l[3]}</td>
          </tr>
        ))}
      </table>
    </div>
  )
}
