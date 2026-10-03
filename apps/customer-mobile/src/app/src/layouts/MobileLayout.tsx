import { NavLink, Outlet, useLocation } from "react-router";
import { Home, Coffee, ShoppingBag, User } from "lucide-react";
import { useCart } from "../context/CartContext";

export default function MobileLayout() {
  const location = useLocation();
  const { items } = useCart();
  const cartCount = items.reduce((acc, item) => acc + item.quantity, 0);

  const navItems = [
    { name: "홈", path: "/", icon: Home },
    { name: "오더", path: "/order", icon: Coffee },
    { name: "장바구니", path: "/cart", icon: ShoppingBag, badge: cartCount },
    { name: "마이페이지", path: "/profile", icon: User },
  ];

  // Hide bottom nav on specific pages like product detail
  const hideBottomNav = location.pathname.startsWith("/product/");

  return (
    <div className="flex justify-center bg-zinc-100 min-h-[100dvh] dark:bg-black">
      <div className="w-full max-w-[480px] bg-white dark:bg-zinc-950 h-[100dvh] relative shadow-2xl flex flex-col overflow-hidden">
        
        {/* Dynamic Island / Status Bar Space */}
        <div className="w-full h-[max(env(safe-area-inset-top),47px)] shrink-0 bg-white dark:bg-zinc-950 z-50 flex justify-center items-start pt-2 pointer-events-none relative">
          {/* iOS Dynamic Island mock for preview context */}
          <div className="w-[120px] h-[32px] bg-black rounded-full shadow-sm hidden md:block"></div>
        </div>

        {/* Main Content Area */}
        <main 
          className="flex-1 overflow-y-auto no-scrollbar"
          style={{ paddingBottom: hideBottomNav ? 'max(env(safe-area-inset-bottom), 34px)' : 'calc(70px + max(env(safe-area-inset-bottom), 34px))' }}
        >
          <Outlet />
        </main>

        {/* Bottom Navigation */}
        {!hideBottomNav && (
          <nav 
            className="absolute bottom-0 left-0 right-0 bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-800 px-6 pt-2 flex justify-between items-center z-50"
            style={{ paddingBottom: 'calc(max(env(safe-area-inset-bottom), 34px) + 12px)' }}
          >
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || 
                (item.path === '/order' && location.pathname.startsWith('/order'));
                
              return (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className="flex flex-col items-center gap-1 w-16"
                >
                  <div className="relative">
                    <item.icon
                      size={24}
                      strokeWidth={isActive ? 2.5 : 2}
                      className={`transition-colors duration-200 ${
                        isActive
                          ? "text-[#E09D00]"
                          : "text-zinc-400 dark:text-zinc-500"
                      }`}
                    />
                    {item.badge ? (
                      <span className="absolute -top-1 -right-2 bg-red-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                        {item.badge}
                      </span>
                    ) : null}
                  </div>
                  <span
                    className={`text-[10px] transition-colors duration-200 mt-1 ${
                      isActive
                        ? "text-[#E09D00] font-medium"
                        : "text-zinc-500 dark:text-zinc-500"
                    }`}
                  >
                    {item.name}
                  </span>
                </NavLink>
              );
            })}
          </nav>
        )}

        {/* iOS Home Indicator mock for preview context */}
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-[134px] h-[5px] bg-black/20 dark:bg-white/20 rounded-full z-[60] pointer-events-none hidden md:block" />
      </div>
    </div>
  );
}
