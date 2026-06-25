import { createContext, useContext, useState } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [activeApplication, setActiveApplication] = useState(null)

  return (
    <AppContext.Provider value={{ activeApplication, setActiveApplication }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  return useContext(AppContext)
}
