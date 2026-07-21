import { useState, useContext, createContext, useCallback } from 'react';

interface LoadingState {
  count: number;
  increment: () => void;
  decrement: () => void;
}

const LoadingContext = createContext<LoadingState>({
  count: 0,
  increment: () => {},
  decrement: () => {},
});

export function LoadingProvider({ children }: { children: React.ReactNode }) {
  const [count, setCount] = useState(0);

  const increment = useCallback(() => setCount(c => c + 1), []);
  const decrement = useCallback(() => setCount(c => Math.max(0, c - 1)), []);

  return (
    <LoadingContext.Provider value={{ count, increment, decrement }}>
      {children}
    </LoadingContext.Provider>
  );
}

export function useLoading() {
  const { count, increment, decrement } = useContext(LoadingContext);
  return {
    isLoading: count > 0,
    loadingCount: count,
    increment,
    decrement,
  };
}