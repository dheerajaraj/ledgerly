import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import { api, tokenStore } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
	const [user, setUser] = useState(null);
	const [ready, setReady] = useState(false);

	const signOut = useCallback(() => {
		tokenStore.clear();
		setUser(null);
	}, []);

	useEffect(() => {
		if (!tokenStore.get()) return setReady(true);
		api
			.me()
			.then(setUser)
			.catch(signOut)
			.finally(() => setReady(true));
	}, [signOut]);

	useEffect(() => {
		window.addEventListener("ledgerly:unauthorized", signOut);
		return () => window.removeEventListener("ledgerly:unauthorized", signOut);
	}, [signOut]);

	const finish = ({ access_token, user }) => {
		tokenStore.set(access_token);
		setUser(user);
	};

	const value = {
		user,
		ready,
		signIn: async (email, password) =>
			finish(await api.login({ email, password })),
		register: async (name, email, password) =>
			finish(await api.register({ name, email, password })),
		signOut,
	};
	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
