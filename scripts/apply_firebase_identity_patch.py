from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "apps/customer-mobile/src/CustomerMobileApp.tsx"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, found {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    if "type CustomerMobileAppProps" in text:
        print("Firebase identity patch is already applied.")
        return

    text = replace_once(
        text,
        "import React, { useMemo, useState } from 'react';",
        "import React, { useEffect, useMemo, useState } from 'react';",
    )
    text = replace_once(
        text,
        "\nconst CUSTOMER_ID = 'demo-customer';\nconst CUSTOMER_NAME = '단호박';\n",
        "\ntype CustomerMobileAppProps = {\n  customerId: string;\n  customerName: string;\n};\n",
    )
    text = replace_once(
        text,
        "export default function CustomerMobileApp() {",
        "export default function CustomerMobileApp({ customerId, customerName }: CustomerMobileAppProps) {",
    )
    text = text.replace("submitAppOrder(orderedItems, CUSTOMER_ID)", "submitAppOrder(orderedItems, customerId)")
    text = text.replace("customer_id: CUSTOMER_ID", "customer_id: customerId")
    text = text.replace("name: CUSTOMER_NAME", "name: customerName")

    state_anchor = "  const [faceError, setFaceError] = useState('');\n\n"
    sync_block = """  const [faceError, setFaceError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const syncFirebaseCustomerToJetson = async () => {
      const defaultMenu = MENU_DATA[0];
      if (!defaultMenu) return;

      try {
        const ensured = await ensureCustomer({
          customer_id: customerId,
          name: customerName,
          preferred_menu: defaultMenu.name,
          preferred_temperature: 'ICE',
          preferred_quantity: 1,
        });
        const status = await getFaceEnrollment(ensured.customer_id);
        if (cancelled) return;
        setCustomer(ensured);
        setEnrollment(status);
      } catch (error) {
        if (!cancelled) setFaceError(errorMessage(error));
      }
    };

    void syncFirebaseCustomerToJetson();
    return () => {
      cancelled = true;
    };
  }, [customerId, customerName]);

"""
    text = replace_once(text, state_anchor, sync_block)

    text = text.replace(
        "<HomeScreen onNavigate={setScreen} onSelectMenu={openDetail} />",
        "<HomeScreen customerName={customerName} onNavigate={setScreen} onSelectMenu={openDetail} />",
    )
    text = replace_once(
        text,
        "function HomeScreen({ onNavigate, onSelectMenu }: { onNavigate: (screen: AppScreen) => void; onSelectMenu: (menu: MenuItem) => void }) {",
        "function HomeScreen({ customerName, onNavigate, onSelectMenu }: { customerName: string; onNavigate: (screen: AppScreen) => void; onSelectMenu: (menu: MenuItem) => void }) {",
    )
    text = replace_once(
        text,
        "<Text style={styles.hello}>안녕하세요, <Text style={styles.yellow}>단호박</Text> 님</Text>",
        "<Text style={styles.hello}>안녕하세요, <Text style={styles.yellow}>{customerName}</Text> 님</Text>",
    )

    TARGET.write_text(text, encoding="utf-8")
    print(f"Patched: {TARGET}")


if __name__ == "__main__":
    main()
