"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Loader2, Plus, Wallet as WalletIcon } from "lucide-react";

import {
  walletApi,
  type TeamWallet,
  type WalletCreateRequest,
} from "@/lib/api";
import { toast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const PROVIDERS: { value: string; label: string; hint: string }[] = [
  {
    value: "cdp",
    label: "Coinbase Server Wallet",
    hint: "Custodied by Coinbase Developer Platform",
  },
  {
    value: "native",
    label: "Native Wallet",
    hint: "Key generated and stored by the platform",
  },
  {
    value: "safe",
    label: "Safe Wallet",
    hint: "Safe smart account with spending limits",
  },
  { value: "privy", label: "Privy Wallet", hint: "Privy server wallet" },
  {
    value: "readonly",
    label: "Readonly Wallet",
    hint: "Watch an existing address, no signing",
  },
];

const NETWORKS = [
  "base-mainnet",
  "ethereum-mainnet",
  "polygon-mainnet",
  "arbitrum-mainnet",
  "optimism-mainnet",
  "bnb-mainnet",
  "base-sepolia",
];

function shortAddress(address: string): string {
  if (address.length <= 14) return address;
  return `${address.slice(0, 8)}…${address.slice(-6)}`;
}

function WalletCard({ wallet }: { wallet: TeamWallet }) {
  const provider = PROVIDERS.find((p) => p.value === wallet.wallet_provider);

  const copyAddress = () => {
    if (!wallet.evm_wallet_address) return;
    navigator.clipboard.writeText(wallet.evm_wallet_address);
    toast({ title: "Address copied", variant: "success" });
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <WalletIcon className="h-4 w-4 text-muted-foreground" />
            {wallet.name}
          </CardTitle>
          <Badge variant="secondary">
            {provider?.label ?? wallet.wallet_provider}
          </Badge>
        </div>
        {wallet.network_id ? (
          <CardDescription>{wallet.network_id}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent>
        {wallet.evm_wallet_address ? (
          <button
            type="button"
            onClick={copyAddress}
            className="flex items-center gap-1.5 font-mono text-sm text-muted-foreground hover:text-foreground"
            title={wallet.evm_wallet_address}
          >
            {shortAddress(wallet.evm_wallet_address)}
            <Copy className="h-3.5 w-3.5" />
          </button>
        ) : (
          <p className="text-sm text-muted-foreground">No address</p>
        )}
        {wallet.weekly_spending_limit != null ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Weekly limit: {wallet.weekly_spending_limit} USDC
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function CreateWalletForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("cdp");
  const [network, setNetwork] = useState("base-mainnet");
  const [readonlyAddress, setReadonlyAddress] = useState("");
  const [spendingLimit, setSpendingLimit] = useState("");

  const providerHint = PROVIDERS.find((p) => p.value === provider)?.hint;

  const createMutation = useMutation({
    mutationFn: (body: WalletCreateRequest) => walletApi.createWallet(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
      toast({ title: "Wallet created", variant: "success" });
      onDone();
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to create wallet",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const submit = () => {
    if (!name.trim()) {
      toast({ title: "Wallet name is required", variant: "destructive" });
      return;
    }
    createMutation.mutate({
      name: name.trim(),
      wallet_provider: provider,
      network_id: network,
      readonly_address:
        provider === "readonly" ? readonlyAddress.trim() || null : null,
      weekly_spending_limit:
        provider === "safe" && spendingLimit ? Number(spendingLimit) : null,
    });
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">New Wallet</CardTitle>
        <CardDescription>
          Wallets are shared team resources. Authorize an agent to use one by
          setting its Team Wallet field.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2">
          <label htmlFor="wallet-name" className="text-sm font-medium">
            Name
          </label>
          <Input
            id="wallet-name"
            value={name}
            maxLength={50}
            placeholder="e.g. trading"
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <label htmlFor="wallet-provider" className="text-sm font-medium">
            Provider
          </label>
          <select
            id="wallet-provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          {providerHint ? (
            <p className="text-xs text-muted-foreground">{providerHint}</p>
          ) : null}
        </div>
        <div className="grid gap-2">
          <label htmlFor="wallet-network" className="text-sm font-medium">
            Network
          </label>
          <select
            id="wallet-network"
            value={network}
            onChange={(e) => setNetwork(e.target.value)}
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm"
          >
            {NETWORKS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        {provider === "readonly" ? (
          <div className="grid gap-2">
            <label htmlFor="wallet-address" className="text-sm font-medium">
              Address to watch
            </label>
            <Input
              id="wallet-address"
              value={readonlyAddress}
              placeholder="0x…"
              onChange={(e) => setReadonlyAddress(e.target.value)}
            />
          </div>
        ) : null}
        {provider === "safe" ? (
          <div className="grid gap-2">
            <label htmlFor="wallet-limit" className="text-sm font-medium">
              Weekly spending limit (USDC)
            </label>
            <Input
              id="wallet-limit"
              type="number"
              min="0"
              value={spendingLimit}
              placeholder="Optional"
              onChange={(e) => setSpendingLimit(e.target.value)}
            />
          </div>
        ) : null}
        <div className="flex gap-2">
          <Button onClick={submit} disabled={createMutation.isPending}>
            {createMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Create
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ClientPage() {
  const [creating, setCreating] = useState(false);

  const { data: wallets, isLoading } = useQuery({
    queryKey: ["wallets"],
    queryFn: () => walletApi.listWallets(),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Crypto Wallets</h1>
          <p className="text-sm text-muted-foreground">
            Wallets owned by this deployment. Agents can be authorized to use
            them.
          </p>
        </div>
        {!creating ? (
          <Button onClick={() => setCreating(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Wallet
          </Button>
        ) : null}
      </div>

      {creating ? <CreateWalletForm onDone={() => setCreating(false)} /> : null}

      {isLoading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : wallets && wallets.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {wallets.map((wallet) => (
            <WalletCard key={wallet.id} wallet={wallet} />
          ))}
        </div>
      ) : !creating ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No wallets yet. Create one to let your agents act on-chain.
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
