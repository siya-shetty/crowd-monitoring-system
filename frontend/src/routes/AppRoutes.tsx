import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '../auth/ProtectedRoute'
import { AppShell } from '../layouts/AppShell'
import { DashboardPage } from '../pages/DashboardPage'
import { LoginPage } from '../pages/LoginPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { RegisterPage } from '../pages/RegisterPage'
import { AlertsPage } from '../pages/AlertsPage'
import { VideosPage } from '../pages/VideosPage'
const pages=[['live','Live Monitoring','Camera streams and real-time aggregate crowd metrics will appear here once live monitoring is introduced.'],['analytics','Analytics','Historical crowd trends and reporting will be available here in a future phase.'],['events','Events','Create and manage monitored events once event workflows are introduced.'],['incidents','Incidents','Incident triage and resolution workflows will be available here in a future phase.'],['cameras','Cameras','Connect and manage camera sources here. Live capture is not enabled in Phase 1.'],['settings','Settings','Manage account, notification, and system preferences when authentication is implemented.']] as const
export function AppRoutes(){return <Routes><Route path="/login" element={<LoginPage/>}/><Route path="/register" element={<RegisterPage/>}/><Route element={<ProtectedRoute/>}><Route element={<AppShell/>}><Route path="/dashboard" element={<DashboardPage/>}/><Route path="/videos" element={<VideosPage/>}/><Route path="/alerts" element={<AlertsPage/>}/>{pages.map(([path,title,description])=><Route key={path} path={`/${path}`} element={<PlaceholderPage title={title} description={description}/>}/>)}</Route></Route><Route path="*" element={<Navigate to="/dashboard" replace/>}/></Routes>}
