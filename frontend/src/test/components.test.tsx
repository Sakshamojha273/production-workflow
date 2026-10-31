import { act, render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LoginPage } from '../pages/LoginPage'
import { api } from '../services/api'
import { BrowserRouter } from 'react-router-dom'
import { KPICard } from '../components/KPICard'
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  getOrderStatusColor,
  getPriorityColor,
  getStatusColor,
} from '../utils/helpers'

vi.mock('../services/api')

const renderWithRouter = (component: React.ReactNode) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login form', () => {
    renderWithRouter(<LoginPage />)
    
    expect(screen.getByText('SmartPlan AI')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows error on failed login', async () => {
    vi.mocked(api.login).mockRejectedValue(new Error('Invalid credentials'))
    
    renderWithRouter(<LoginPage />)
    
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'wrong@email.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
    
    await screen.findByText('Invalid credentials')
  })

  it('calls demo login on demo button click', async () => {
    vi.mocked(api.demoLogin).mockResolvedValue({ access_token: 'test-token' })
    
    renderWithRouter(<LoginPage />)
    
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/use demo credentials/i))
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
      await vi.waitFor(() => expect(api.demoLogin).toHaveBeenCalled())
    })
  })

  it('toggles password visibility', () => {
    renderWithRouter(<LoginPage />)
    
    const passwordInput = screen.getByLabelText('Password')
    expect(passwordInput).toHaveAttribute('type', 'password')
    
    fireEvent.click(screen.getByRole('button', { name: /show password/i }))
    expect(passwordInput).toHaveAttribute('type', 'text')
    
    fireEvent.click(screen.getByRole('button', { name: /hide password/i }))
    expect(passwordInput).toHaveAttribute('type', 'password')
  })
})

describe('KPICard', () => {
  it('renders with correct values', () => {
    render(
      <KPICard
        title="Test KPI"
        value="100"
        trend={5.2}
        description="Test description"
        status="Healthy"
      />
    )
    
    expect(screen.getByText('Test KPI')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('Test description')).toBeInTheDocument()
    expect(screen.getByText('Healthy')).toBeInTheDocument()
  })

  it('shows up trend correctly', () => {
    render(
      <KPICard
        title="Test KPI"
        value="100"
        trend={5.2}
      />
    )
    
    expect(screen.getByText('+5.2%')).toBeInTheDocument()
  })

  it('shows down trend correctly', () => {
    render(
      <KPICard
        title="Test KPI"
        value="100"
        trend={-3.1}
      />
    )
    
    expect(screen.getByText('-3.1%')).toBeInTheDocument()
  })
})

describe('helpers', () => {
  it('formats numbers correctly', () => {
    expect(formatNumber(1000)).toBe('1K')
    expect(formatNumber(1000000)).toBe('1M')
    expect(formatNumber(500)).toBe('500')
    
    expect(formatCurrency(1000)).toBe('$1,000')
    expect(formatCurrency(1000000)).toBe('$1,000,000')
    
    expect(formatPercent(5.2)).toBe('+5.2%')
    expect(formatPercent(-3.1)).toBe('-3.1%')
  })

  it('gets correct status colors', () => {
    expect(getStatusColor('Healthy')).toContain('bg-success-100')
    expect(getStatusColor('Warning')).toContain('bg-warning-100')
    expect(getStatusColor('Critical')).toContain('bg-danger-100')
    
    expect(getPriorityColor('High')).toContain('bg-danger-100')
    expect(getPriorityColor('Medium')).toContain('bg-warning-100')
    expect(getPriorityColor('Low')).toContain('bg-success-100')
    
    expect(getOrderStatusColor('Completed')).toContain('bg-success-100')
    expect(getOrderStatusColor('Delayed')).toContain('bg-danger-100')
  })
})