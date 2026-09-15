import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'
test('redirects an unauthenticated visitor to login', async () => {
  localStorage.clear()
  render(<MemoryRouter initialEntries={['/dashboard']}><AuthProvider><Routes><Route path="/login" element={<p>Login screen</p>}/><Route element={<ProtectedRoute/>}><Route path="/dashboard" element={<p>Dashboard</p>}/></Route></Routes></AuthProvider></MemoryRouter>)
  expect(await screen.findByText('Login screen')).toBeInTheDocument()
})
