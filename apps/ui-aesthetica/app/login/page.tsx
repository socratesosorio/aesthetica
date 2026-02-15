import { Suspense } from 'react'

import LoginClient from './login-client'

export default function LoginPage() {
  return (
    <Suspense>
      <LoginClient />
    </Suspense>
  )
}

