import { createContext, useContext, useState, type ReactNode } from "react"

interface OperatorContextType {
  selectedOperator: string | null
  setSelectedOperator: (op: string | null) => void
}

const OperatorContext = createContext<OperatorContextType | undefined>(undefined)

export function OperatorProvider({ children }: { children: ReactNode }) {
  const [selectedOperator, setSelectedOperator] = useState<string | null>(null)

  return (
    <OperatorContext.Provider value={{ selectedOperator, setSelectedOperator }}>
      {children}
    </OperatorContext.Provider>
  )
}

export function useOperator(): OperatorContextType {
  const context = useContext(OperatorContext)
  if (context === undefined) {
    throw new Error("useOperator must be used within an OperatorProvider")
  }
  return context
}
