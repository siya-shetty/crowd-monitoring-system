import { render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet } from 'react-router-dom'
import { vi } from 'vitest'
import { AppRoutes } from './AppRoutes'

vi.mock('../auth/ProtectedRoute', () => ({ ProtectedRoute: () => <Outlet /> }))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: { full_name: 'Operator', role: 'operator' }, logout: vi.fn() }) }))
vi.mock('../pages/IncidentsPage', () => ({ IncidentsPage: () => <h1>Incident workspace</h1> }))
vi.mock('../pages/DashboardPage', () => ({ DashboardPage: () => <h1>Dashboard</h1> }))

test('Incidents remains routed and navigation has no Events entry', async () => {
  render(<MemoryRouter initialEntries={['/incidents']}><AppRoutes /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'Incident workspace' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Incidents' })).toHaveAttribute('href', '/incidents')
  expect(screen.queryByRole('link', { name: 'Events' })).not.toBeInTheDocument()
})

test('retired Events URL uses the existing unknown-route fallback', async () => {
  render(<MemoryRouter initialEntries={['/events']}><AppRoutes /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Events' })).not.toBeInTheDocument()
})
