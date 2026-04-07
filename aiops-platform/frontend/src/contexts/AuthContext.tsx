import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { userApi } from '../services/api';
import type { UserInfo, LoginParams } from '../types';

interface AuthContextType {
  user: UserInfo | null;
  token: string | null;
  loading: boolean;
  login: (params: LoginParams) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  const getUserInfo = useCallback(async () => {
    try {
      const userInfo = await userApi.getUserInfo();
      setUser(userInfo);
    } catch (error) {
      console.error('获取用户信息失败', error);
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      getUserInfo();
    } else {
      setLoading(false);
    }
  }, [token, getUserInfo]);

  const login = useCallback(async (params: LoginParams) => {
    const result = await userApi.login(params);
    localStorage.setItem('token', result.token);
    setToken(result.token);
    setUser(result.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    userApi.logout().catch(console.error);
  }, []);

  const isAdmin = user?.isAdmin || false;

  const hasPermission = useCallback(
    (permission: string) => {
      if (isAdmin) return true;
      return user?.permissions.includes(permission) || false;
    },
    [isAdmin, user?.permissions]
  );

  const hasRole = useCallback(
    (role: string) => {
      if (isAdmin) return true;
      return user?.roles.includes(role) || false;
    },
    [isAdmin, user?.roles]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        isAdmin,
        hasPermission,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
