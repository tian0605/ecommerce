import { createContext, useContext } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchAuthSession, loginSession, logoutSession } from './api';
import type { AuthSessionView, LoginPayload } from './types';

type AuthContextValue = {
  session: AuthSessionView;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<AuthSessionView>;
  logout: () => Promise<AuthSessionView>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider(props: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ['auth-session'],
    queryFn: fetchAuthSession,
    staleTime: 60_000,
  });

  const loginMutation = useMutation({
    mutationFn: loginSession,
    onSuccess: (session) => {
      queryClient.setQueryData(['auth-session'], session);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logoutSession,
    onSuccess: (session) => {
      queryClient.setQueryData(['auth-session'], session);
      queryClient.invalidateQueries({ queryKey: ['system-configs'] });
      queryClient.invalidateQueries({ queryKey: ['product-detail'] });
    },
  });

  return (
    <AuthContext.Provider value={{
      session: sessionQuery.data ?? { authenticated: false, user: null },
      isLoading: sessionQuery.isLoading || loginMutation.isPending || logoutMutation.isPending,
      login: (payload) => loginMutation.mutateAsync(payload),
      logout: () => logoutMutation.mutateAsync(),
    }}>
      {props.children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}