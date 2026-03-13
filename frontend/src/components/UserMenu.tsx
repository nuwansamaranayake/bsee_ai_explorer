import { LogOut, User, Shield } from "lucide-react"
import { useAuth } from "@/contexts/AuthContext"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

/**
 * UserMenu — dropdown in the sidebar footer showing logged-in user
 * with role badge and Sign Out option.
 */
export function UserMenu() {
  const { user, logout } = useAuth()

  if (!user) return null

  // First letter(s) of name as avatar initials
  const initials = user.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 h-auto py-2"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-600 text-white text-xs font-medium">
            {initials}
          </div>
          <div className="flex flex-col items-start text-left min-w-0">
            <span className="text-sm font-medium truncate w-full">
              {user.name}
            </span>
            <span className="text-[11px] text-muted-foreground truncate w-full">
              {user.email}
            </span>
          </div>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <div className="flex flex-col">
              <span className="text-sm font-medium">{user.name}</span>
              <span className="text-xs text-muted-foreground">
                {user.email}
              </span>
            </div>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled className="text-xs">
          <Shield className="mr-2 h-3.5 w-3.5" />
          Role: <span className="ml-1 font-medium capitalize">{user.role}</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={logout}
          className="text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400"
        >
          <LogOut className="mr-2 h-4 w-4" />
          Sign Out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
