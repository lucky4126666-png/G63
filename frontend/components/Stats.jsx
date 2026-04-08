function Stats(){
  const ref = React.useRef()

  React.useEffect(()=>{
    new Chart(ref.current, {
      type: 'bar',
      data: {
        labels: ['Admins','Groups','Logs'],
        datasets: [{
          label: 'System',
          data: [5, 10, 20]
        }]
      }
    })
  },[])

  return <canvas ref={ref}></canvas>
}
