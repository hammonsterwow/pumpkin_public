import { createBrowserRouter } from "react-router";
import MobileLayout from "./layouts/MobileLayout";
import Home from "./pages/Home";
import Order from "./pages/Order";
import ProductDetail from "./pages/ProductDetail";
import Cart from "./pages/Cart";

// A dummy Profile component for the bottom nav link
const Profile = () => (
  <div className="p-6 flex flex-col items-center justify-center min-h-[50vh]">
    <div className="w-20 h-20 bg-zinc-200 dark:bg-zinc-800 rounded-full mb-4"></div>
    <h2 className="text-xl font-bold dark:text-white">Impactful님</h2>
    <p className="text-sm text-zinc-500 mt-2">마이페이지 준비중입니다.</p>
  </div>
);

export const router = createBrowserRouter([
  {
    path: "/",
    Component: MobileLayout,
    children: [
      { index: true, Component: Home },
      { path: "order", Component: Order },
      { path: "product/:id", Component: ProductDetail },
      { path: "cart", Component: Cart },
      { path: "profile", Component: Profile },
    ],
  },
]);
