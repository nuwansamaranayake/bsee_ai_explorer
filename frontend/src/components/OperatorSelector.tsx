import { useState } from "react"
import { ChevronsUpDown, Building2 } from "lucide-react"
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useOperators } from "@/hooks/useOperators"
import { useOperator } from "@/contexts/OperatorContext"

export function OperatorSelector() {
  const [open, setOpen] = useState(false)
  const { selectedOperator, setSelectedOperator } = useOperator()
  const { data, isLoading, isError } = useOperators()

  const operators = data?.data ?? []

  const selectedLabel = selectedOperator
    ? operators.find((op) => op.name === selectedOperator)?.name ?? selectedOperator
    : "All GoM Operators"

  if (isLoading) {
    return (
      <div className="px-2 py-2">
        <Skeleton className="h-9 w-full" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="px-2 py-2 text-xs text-destructive">
        Failed to load operators
      </div>
    )
  }

  return (
    <div className="px-2 py-2">
      <Button
        variant="outline"
        size="sm"
        className="w-full justify-between text-left font-normal"
        onClick={() => setOpen(!open)}
      >
        <span className="flex items-center gap-2 truncate">
          <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{selectedLabel}</span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </Button>

      {open && (
        <div className="mt-2 rounded-lg border bg-popover shadow-md">
          <Command>
            <CommandInput placeholder="Search operators..." />
            <CommandList>
              <CommandEmpty>No operators found.</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  value="all-gom-operators"
                  data-checked={selectedOperator === null}
                  onSelect={() => {
                    setSelectedOperator(null)
                    setOpen(false)
                  }}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className="font-medium">All GoM Operators</span>
                  </div>
                </CommandItem>
                {operators.map((op) => (
                  <CommandItem
                    key={op.name}
                    value={op.name}
                    data-checked={selectedOperator === op.name}
                    onSelect={() => {
                      setSelectedOperator(op.name)
                      setOpen(false)
                    }}
                  >
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="truncate">{op.name}</span>
                      <Badge variant="secondary" className="shrink-0 text-[10px]">
                        {op.incident_count} incidents
                      </Badge>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </div>
      )}
    </div>
  )
}
