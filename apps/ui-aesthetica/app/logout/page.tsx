'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import { logout } from '@/lib/api'

export default function LogoutPage() {
  const router = useRouter()

  React.useEffect(() => {
    logout()
    router.replace('/')
  }, [router])

  return null
}

