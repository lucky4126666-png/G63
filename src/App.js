async function register(){
  await fetch("/register",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      username:document.getElementById("user").value,
      password:document.getElementById("pass").value
    })
  })
  alert("Registered")
}

async function login(){
  let res = await fetch("/login",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      username:document.getElementById("user").value,
      password:document.getElementById("pass").value
    })
  })
  let data = await res.json()
  alert(data.ok ? "Login OK":"Fail")
}
