'use client'

import * as React from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, getStoredToken, loginWithPassword, logout } from '@/lib/api'

export default function LoginClient() {
  const router = useRouter()
  const params = useSearchParams()
  const next = params.get('next') || '/profile'

  const [email, setEmail] = React.useState(process.env.NEXT_PUBLIC_DEV_AUTH_EMAIL ?? '')
  const [password, setPassword] = React.useState(process.env.NEXT_PUBLIC_DEV_AUTH_PASSWORD ?? '')
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    const ctrl = new AbortController()
    async function maybeSkip() {
      const token = getStoredToken()
      if (!token) return
      try {
        await api.me(token, ctrl.signal)
        router.replace(next)
      } catch {
        logout()
      }
    }
    maybeSkip()
    return () => ctrl.abort()
  }, [next, router])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await loginWithPassword(email.trim(), password, undefined)
      router.replace(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex min-h-screen w-full max-w-xl flex-col justify-center px-4 py-16">
        <div className="mb-8 flex items-center justify-center gap-3">
          <Link href="/" aria-label="Aesthetica" className="flex items-center gap-3">
            <span className="block size-10 overflow-hidden rounded-xl border border-border bg-muted">
              <Image src="/logo.png" alt="Aesthetica" width={40} height={40} className="h-10 w-10 object-cover" />
            </span>
            <span className="text-sm text-muted-foreground">Sign in</span>
          </Link>
        </div>

        <Card className="overflow-hidden">
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl md:text-3xl">Welcome back</CardTitle>
            <CardDescription>
              Sign in to view captures, matches, and your taste radar.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              {error ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

              <Button type="submit" className="h-10" disabled={loading}>
                {loading ? 'Signing in…' : 'Sign in'}
              </Button>

              <div className="text-muted-foreground text-center text-xs">
                <Link href="/" className="underline underline-offset-4 hover:text-foreground">
                  Back to landing
                </Link>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

