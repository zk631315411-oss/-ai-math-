import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { LoadingProvider } from './hooks/useLoading'
import { ToastProvider } from './hooks/useToast'
import ToastContainer from './components/Toast'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LoadingProvider>
      <ToastProvider>
        <App />
        <ToastContainer />
      </ToastProvider>
    </LoadingProvider>
  </React.StrictMode>,
)