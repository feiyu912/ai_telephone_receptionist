import {
  Activity,
  Building2,
  HelpCircle,
  LayoutDashboard,
  Link2,
  Phone,
  Settings,
  Users,
} from "lucide-react";

export type NavSubItem = { title: string; url: string };

export type NavItem = {
  title: string;
  url?: string;
  icon: React.ComponentType<{ className?: string }>;
  items: NavSubItem[];
};

export type NavSection = {
  label: string;
  items: NavItem[];
  adminOnly?: boolean;
};

export const NAV_DATA: NavSection[] = [
  {
    label: "MAIN MENU",
    items: [
      { title: "Overview",     url: "/overview",  icon: LayoutDashboard, items: [] },
      { title: "Call History", url: "/calls",     icon: Phone,           items: [] },
      { title: "Customers",    url: "/customers", icon: Users,           items: [] },
      { title: "FAQ",          url: "/faq",       icon: HelpCircle,      items: [] },
    ],
  },
  {
    label: "CONFIGURATION",
    items: [
      { title: "Settings",     url: "/settings",     icon: Settings, items: [] },
      { title: "Integrations", url: "/integrations", icon: Link2,    items: [] },
    ],
  },
  {
    label: "ADMIN",
    adminOnly: true,
    items: [
      { title: "All Tenants",   url: "/tenants", icon: Building2, items: [] },
      { title: "System Health", url: "/system",  icon: Activity,  items: [] },
    ],
  },
];
