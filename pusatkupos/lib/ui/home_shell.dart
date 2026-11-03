import 'package:flutter/material.dart';

import '../state/app_state.dart';
import 'screens/customers_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/history_screen.dart';
import 'screens/jasa_screen.dart';
import 'screens/pos_screen.dart';
import 'screens/reports_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/stock_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  int _index = 0;

  static const _labels = [
    'Ringkasan',
    'Kasir',
    'Riwayat',
    'Pelanggan',
    'Stok',
    'Jasa',
    'Laporan',
    'Pengaturan',
  ];
  static const _icons = [
    Icons.dashboard_outlined,
    Icons.point_of_sale_outlined,
    Icons.history,
    Icons.people_outline,
    Icons.inventory_2_outlined,
    Icons.build_outlined,
    Icons.bar_chart_outlined,
    Icons.settings_outlined,
  ];

  void _go(int index) {
    if (index < 0 || index >= _labels.length) return;
    setState(() => _index = index);
  }

  List<Widget> _screens() => [
        DashboardScreen(onNavigate: _go),
        const PosScreen(),
        const HistoryScreen(),
        const CustomersScreen(),
        const StockScreen(),
        const JasaScreen(),
        const ReportsScreen(),
        const SettingsScreen(),
      ];

  @override
  Widget build(BuildContext context) {
    final appState = AppState.instance;
    return AnimatedBuilder(
      animation: appState,
      builder: (context, _) {
        final wide = MediaQuery.sizeOf(context).width >= 900;
        final body = IndexedStack(index: _index, children: _screens());
        return Scaffold(
          key: _scaffoldKey,
          drawer: _buildDrawer(context),
          appBar: AppBar(
            title: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _labels[_index],
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                Text(
                  appState.storeAddress.isEmpty
                      ? appState.storeName
                      : '${appState.storeName} · ${appState.storeAddress}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
            actions: [
              IconButton(
                tooltip: 'Ganti tema',
                onPressed: () {
                  final dark = Theme.of(context).brightness == Brightness.dark;
                  appState.setThemeMode(
                    dark ? ThemeMode.light : ThemeMode.dark,
                  );
                },
                icon: Icon(
                  Theme.of(context).brightness == Brightness.dark
                      ? Icons.light_mode_outlined
                      : Icons.dark_mode_outlined,
                ),
              ),
              const SizedBox(width: 6),
            ],
          ),
          body: wide
              ? Row(
                  children: [
                    NavigationRail(
                      selectedIndex: _index,
                      extended: MediaQuery.sizeOf(context).width >= 1180,
                      labelType: MediaQuery.sizeOf(context).width >= 1180
                          ? NavigationRailLabelType.none
                          : NavigationRailLabelType.all,
                      onDestinationSelected: (value) =>
                          setState(() => _index = value),
                      leading: Padding(
                        padding: const EdgeInsets.only(top: 8, bottom: 12),
                        child: Icon(
                          Icons.storefront_outlined,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                      destinations: [
                        for (var i = 0; i < _labels.length; i++)
                          NavigationRailDestination(
                            icon: Icon(_icons[i]),
                            selectedIcon: Icon(
                              _icons[i],
                              color: Theme.of(context).colorScheme.primary,
                            ),
                            label: Text(_labels[i]),
                          ),
                      ],
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(child: body),
                  ],
                )
              : body,
          bottomNavigationBar: wide
              ? null
              : NavigationBar(
                  selectedIndex: _index <= 2 ? _index : 3,
                  onDestinationSelected: (value) {
                    if (value == 3) {
                      _scaffoldKey.currentState?.openDrawer();
                    } else {
                      setState(() => _index = value);
                    }
                  },
                  destinations: const [
                    NavigationDestination(
                      icon: Icon(Icons.dashboard_outlined),
                      selectedIcon: Icon(Icons.dashboard),
                      label: 'Ringkasan',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.point_of_sale_outlined),
                      selectedIcon: Icon(Icons.point_of_sale),
                      label: 'Kasir',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.history),
                      selectedIcon: Icon(Icons.history),
                      label: 'Riwayat',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.menu),
                      label: 'Menu',
                    ),
                  ],
                ),
        );
      },
    );
  }

  Widget _buildDrawer(BuildContext context) {
    final appState = AppState.instance;
    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 18, 18, 10),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 22,
                    child: Icon(
                      Icons.storefront_outlined,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          appState.storeName,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        Text(
                          appState.storeAddress.isEmpty
                              ? 'PusatkuPOS'
                              : appState.storeAddress,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const Divider(),
            Expanded(
              child: ListView.builder(
                itemCount: _labels.length,
                itemBuilder: (context, index) => ListTile(
                  selected: _index == index,
                  leading: Icon(_icons[index]),
                  title: Text(_labels[index]),
                  onTap: () {
                    _go(index);
                    Navigator.of(context).pop();
                  },
                ),
              ),
            ),
            const Divider(),
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'PusatkuPOS · mode lokal',
                style: TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
