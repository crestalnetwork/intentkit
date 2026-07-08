"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Copy,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Wallet as WalletIcon,
  X,
} from "lucide-react";

import {
  walletApi,
  type TeamWallet,
  type WalletCreateRequest,
} from "@/lib/api";
import { toast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
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

const DEFAULT_NETWORK = NETWORKS[0];

function shortAddress(address: string): string {
  if (address.length <= 14) return address;
  return `${address.slice(0, 8)}…${address.slice(-6)}`;
}

function WalletCard({ wallet }: { wallet: TeamWallet }) {
  const queryClient = useQueryClient();
  const provider = PROVIDERS.find((p) => p.value === wallet.wallet_provider);
  const [editing, setEditing] = useState(false);
  const [newName, setNewName] = useState(wallet.name);

  const copyAddress = () => {
    if (!wallet.evm_wallet_address) return;
    navigator.clipboard.writeText(wallet.evm_wallet_address);
    toast({ title: "Address copied", variant: "success" });
  };

  const renameMutation = useMutation({
    mutationFn: (name: string) => walletApi.updateWallet(wallet.id, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
      toast({ title: "Wallet renamed", variant: "success" });
      setEditing(false);
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to rename wallet",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const networkMutation = useMutation({
    mutationFn: (default_network_id: string) =>
      walletApi.updateWallet(wallet.id, { default_network_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
      toast({ title: "Default network updated", variant: "success" });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to update default network",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => walletApi.deleteWallet(wallet.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
      toast({ title: "Wallet deleted", variant: "success" });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to delete wallet",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const submitRename = () => {
    if (renameMutation.isPending) return;
    const name = newName.trim();
    if (!name || name === wallet.name) {
      setEditing(false);
      setNewName(wallet.name);
      return;
    }
    renameMutation.mutate(name);
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          {editing ? (
            <div className="flex flex-1 items-center gap-1.5">
              <Input
                value={newName}
                maxLength={50}
                className="h-8"
                autoFocus
                disabled={renameMutation.isPending}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitRename();
                  if (e.key === "Escape") {
                    setEditing(false);
                    setNewName(wallet.name);
                  }
                }}
              />
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={submitRename}
                disabled={renameMutation.isPending}
              >
                {renameMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                disabled={renameMutation.isPending}
                onClick={() => {
                  setEditing(false);
                  setNewName(wallet.name);
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <CardTitle className="flex items-center gap-2 text-base">
              <WalletIcon className="h-4 w-4 text-muted-foreground" />
              {wallet.name}
            </CardTitle>
          )}
          {!editing ? (
            <Badge variant="secondary">
              {provider?.label ?? wallet.wallet_provider}
            </Badge>
          ) : null}
        </div>
        <div className="text-sm text-muted-foreground">
          <select
            value={
              networkMutation.isPending && networkMutation.variables
                ? networkMutation.variables
                : (wallet.default_network_id ?? DEFAULT_NETWORK)
            }
            disabled={networkMutation.isPending}
            onChange={(e) => networkMutation.mutate(e.target.value)}
            className="cursor-pointer bg-transparent text-xs text-muted-foreground outline-none hover:text-foreground"
            title="Default network for tools using this wallet"
            aria-label="Default network"
          >
            {wallet.default_network_id &&
            !NETWORKS.includes(wallet.default_network_id) ? (
              <option value={wallet.default_network_id}>
                {wallet.default_network_id}
              </option>
            ) : null}
            {NETWORKS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
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
        {!editing ? (
          <div className="mt-3 flex items-center gap-1.5">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              disabled={deleteMutation.isPending}
              onClick={() => {
                setNewName(wallet.name);
                setEditing(true);
              }}
            >
              <Pencil className="mr-1 h-3 w-3" />
              Rename
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? (
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="mr-1 h-3 w-3" />
                  )}
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    Delete wallet &quot;{wallet.name}&quot;?
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    Funds are NOT swept automatically — make sure the wallet
                    is empty first. This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => deleteMutation.mutate()}>
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function CreateWalletForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("cdp");
  const [network, setNetwork] = useState(DEFAULT_NETWORK);
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
      default_network_id: network,
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
          Wallets are shared team resources. Agents with web3 tools pick one
          by address at tool-call time.
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
            Default Network
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
