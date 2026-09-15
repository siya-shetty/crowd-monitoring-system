import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
export function ProtectedRoute() { const { isAuthenticated, isLoading } = useAuth(); const location = useLocation(); if (isLoading) return <main className="route-loading">Checking your secure workspace…</main>; return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} /> }
