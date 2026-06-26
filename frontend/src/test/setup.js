// Vitest global setup: adds jest-dom matchers (toBeInTheDocument, etc.)
// and cleans up the React tree after every test.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
