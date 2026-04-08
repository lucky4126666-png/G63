function AdminTable(){
  const [data,setData] = React.useState([])

  React.useEffect(()=>{
    fetch("/admin/list")
      .then(r=>r.json())
      .then(d=>setData(d.data))
  },[])

  return (
    <div>
      <h2>👥 Admins</h2>
      <table border="1">
        <tr><th>ID</th><th>Role</th></tr>
        {data.map(a=>(
          <tr>
            <td>{a[0]}</td>
            <td>{a[1]}</td>
          </tr>
        ))}
      </table>
    </div>
  )
}
