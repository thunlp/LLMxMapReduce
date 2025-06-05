"use client"

import React, { createContext, useContext, useState, useEffect } from 'react'
import { getUserInfo } from '@/lib/api'

interface User {
  id: number
  phone: string
  remaining_uses: number
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (token: string, user: User) => void
  logout: () => void
  isLoading: boolean
  refreshUserInfo: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // 从localStorage恢复登录状态
    const savedToken = localStorage.getItem('token')
    const savedUser = localStorage.getItem('user')
    
    if (savedToken && savedUser) {
      setToken(savedToken)
      setUser(JSON.parse(savedUser))
      
      // 恢复登录状态后，获取最新的用户信息
      const fetchUserInfo = async () => {
        try {
          const response = await getUserInfo(savedToken)
          if (response.success) {
            const updatedUser = response.data
            setUser(updatedUser)
            localStorage.setItem('user', JSON.stringify(updatedUser))
          }
        } catch (error) {
          console.error('获取用户信息失败:', error)
          // 如果获取用户信息失败，可能token已过期，清除登录状态
          setToken(null)
          setUser(null)
          localStorage.removeItem('token')
          localStorage.removeItem('user')
        }
      }
      
      fetchUserInfo()
    }
    
    setIsLoading(false)
  }, [])

  const refreshUserInfo = async () => {
    if (!token) return
    
    try {
      const response = await getUserInfo(token)
      if (response.success) {
        const updatedUser = response.data
        setUser(updatedUser)
        localStorage.setItem('user', JSON.stringify(updatedUser))
      }
    } catch (error) {
      console.error('刷新用户信息失败:', error)
    }
  }

  const login = (newToken: string, newUser: User) => {
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading, refreshUserInfo }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}