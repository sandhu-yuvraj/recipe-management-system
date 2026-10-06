const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {...options, headers});
  const data = await res.json().catch(()=>({}));
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
export const api = {
  register: (email,password)=>request('/auth/register',{method:'POST',body:JSON.stringify({email,password})}),
  login: (email,password)=>request('/auth/login',{method:'POST',body:JSON.stringify({email,password})}),
  recipes: (q='')=>request(`/recipes${q?`?q=${encodeURIComponent(q)}`:''}`),
  recipe: id=>request(`/recipes/${id}`),
  ingredients: ()=>request('/ingredients'),
  create: body=>request('/recipes',{method:'POST',body:JSON.stringify(body)}),
  update: (id,body)=>request(`/recipes/${id}`,{method:'PUT',body:JSON.stringify(body)}),
  remove: id=>request(`/recipes/${id}`,{method:'DELETE'}),
  addComponent: (id,body)=>request(`/recipes/${id}/components`,{method:'POST',body:JSON.stringify(body)}),
  editComponent:(id,cid,body)=>request(`/recipes/${id}/components/${cid}`,{method:'PUT',body:JSON.stringify(body)}),
  removeComponent:(id,cid)=>request(`/recipes/${id}/components/${cid}`,{method:'DELETE'}),
  expand:id=>request(`/recipes/${id}/expand`),
};
